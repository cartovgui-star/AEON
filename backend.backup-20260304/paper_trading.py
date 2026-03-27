"""
AEON REALISTIC PAPER TRADING SYSTEM
Inspired by MEXC Demo Trading

Features:
- Two accounts: PRO ($50K) and STARTER ($1.5K)
- Liquidation prices
- Leverage, margin, position sizing
- Cross/Isolated margin modes
- Add margin to positions
- Auto-reload on liquidation
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Account configurations
ACCOUNTS = {
    "PRO": {
        "name": "PRO Account",
        "starting_balance": 50000.0,
        "emoji": "👑"
    },
    "STARTER": {
        "name": "Starter Account", 
        "starting_balance": 1500.0,
        "emoji": "🌱"
    }
}

# Default leverage by asset - NO RESTRICTIONS, use what's best
def get_dynamic_leverage(symbol: str, confidence: int, direction: str) -> int:
    """
    Calculate optimal leverage based on confidence and risk
    Higher confidence = higher leverage
    """
    coin = symbol.split("/")[0] if "/" in symbol else symbol
    
    # Base leverage by coin volatility
    base_leverage = {
        "BTC": 25,
        "ETH": 25,
        "SOL": 30,
        "DOGE": 20,
        "XRP": 20,
        "BNB": 25,
        "ADA": 20,
        "AVAX": 25,
        "LINK": 25,
        "DOT": 20,
    }.get(coin, 20)
    
    # Adjust based on confidence
    if confidence >= 90:
        leverage = base_leverage + 25  # High confidence = aggressive
    elif confidence >= 85:
        leverage = base_leverage + 15
    elif confidence >= 80:
        leverage = base_leverage + 5
    else:
        leverage = base_leverage
    
    # Cap at 125x max (like exchanges)
    return min(125, max(10, leverage))


def calculate_liquidation_price(
    entry_price: float,
    leverage: int,
    direction: str,
    margin_type: str = "isolated",
    maintenance_margin_rate: float = 0.005  # 0.5% maintenance margin
) -> float:
    """
    Calculate liquidation price for a position
    
    For LONG: Liq Price = Entry * (1 - 1/Leverage + MMR)
    For SHORT: Liq Price = Entry * (1 + 1/Leverage - MMR)
    """
    if direction == "LONG":
        liq_price = entry_price * (1 - (1 / leverage) + maintenance_margin_rate)
    else:  # SHORT
        liq_price = entry_price * (1 + (1 / leverage) - maintenance_margin_rate)
    
    return round(liq_price, 2)


def calculate_position_size(
    balance: float,
    risk_pct: float,
    entry_price: float,
    stop_loss: float,
    leverage: int
) -> Dict:
    """Calculate position size based on risk"""
    risk_amount = balance * (risk_pct / 100)
    
    # Distance to stop loss
    sl_distance_pct = abs(entry_price - stop_loss) / entry_price * 100
    
    # Position size in USD (notional value)
    if sl_distance_pct > 0:
        position_size_usd = (risk_amount / (sl_distance_pct / 100)) * leverage
    else:
        position_size_usd = balance * 0.1 * leverage  # Fallback: 10% of balance
    
    # Cap at available balance * leverage
    max_position = balance * leverage
    position_size_usd = min(position_size_usd, max_position)
    
    # Calculate margin required
    margin_required = position_size_usd / leverage
    
    # Quantity in coins
    quantity = position_size_usd / entry_price
    
    # Ensure minimum margin of $1 for trades
    margin_required = max(margin_required, 1.0)
    
    return {
        "position_size_usd": round(position_size_usd, 4),
        "margin_required": round(margin_required, 4),
        "quantity": round(quantity, 8),
        "leverage": leverage,
        "risk_amount": round(risk_amount, 4)
    }


class PaperTradingSystem:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.accounts: Dict[str, Dict] = {}
        
    async def initialize(self):
        """Initialize or load paper trading accounts"""
        for acc_id, config in ACCOUNTS.items():
            account = await self.db.paper_accounts.find_one({"_id": acc_id})
            
            if not account:
                # Create new account
                account = {
                    "_id": acc_id,
                    "name": config["name"],
                    "emoji": config["emoji"],
                    "balance": config["starting_balance"],
                    "starting_balance": config["starting_balance"],
                    "total_pnl": 0.0,
                    "total_trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "reloads": 0,
                    "created_at": datetime.now(timezone.utc),
                    "positions": []
                }
                await self.db.paper_accounts.insert_one(account)
                logger.info(f"Created paper account: {acc_id} with ${config['starting_balance']}")
            
            self.accounts[acc_id] = account
        
        logger.info(f"Paper trading initialized: {list(self.accounts.keys())}")
    
    async def get_account(self, account_id: str) -> Optional[Dict]:
        """Get account by ID"""
        account = await self.db.paper_accounts.find_one({"_id": account_id})
        return account
    
    async def get_all_accounts(self) -> List[Dict]:
        """Get all accounts"""
        accounts = await self.db.paper_accounts.find().to_list(10)
        return accounts
    
    async def open_position(
        self,
        account_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        leverage: int = None,
        margin_type: str = "cross",
        risk_pct: float = 2.0,
        signal_data: Dict = None,
        confidence: int = 80
    ) -> Dict:
        """Open a new position with full details"""
        
        account = await self.get_account(account_id)
        if not account:
            return {"error": "Account not found"}
        
        # Get dynamic leverage based on confidence if not specified
        if leverage is None:
            leverage = get_dynamic_leverage(symbol, confidence, direction)
        
        # Calculate position sizing
        sizing = calculate_position_size(
            balance=account["balance"],
            risk_pct=risk_pct,
            entry_price=entry_price,
            stop_loss=stop_loss,
            leverage=leverage
        )
        
        # Check if we have enough balance
        if sizing["margin_required"] > account["balance"]:
            return {"error": f"Insufficient balance. Need ${sizing['margin_required']:.2f}, have ${account['balance']:.2f}"}
        
        # Calculate liquidation price
        liq_price = calculate_liquidation_price(
            entry_price=entry_price,
            leverage=leverage,
            direction=direction,
            margin_type=margin_type
        )
        
        # Calculate R:R ratio
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        rr_ratio = round(reward / risk, 2) if risk > 0 else 0
        
        # Create position
        position = {
            "id": f"{symbol}_{datetime.now().timestamp()}",
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "current_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "liquidation_price": liq_price,
            "leverage": leverage,
            "margin_type": margin_type,
            "margin": sizing["margin_required"],
            "initial_margin": sizing["margin_required"],
            "position_size_usd": sizing["position_size_usd"],
            "quantity": sizing["quantity"],
            "unrealized_pnl": 0.0,
            "unrealized_pnl_pct": 0.0,
            "rr_ratio": rr_ratio,
            "status": "open",
            "opened_at": datetime.now(timezone.utc),
            "signal_data": signal_data or {}
        }
        
        # Update account balance (lock margin)
        new_balance = account["balance"] - sizing["margin_required"]
        
        # Add position to account
        await self.db.paper_accounts.update_one(
            {"_id": account_id},
            {
                "$set": {"balance": new_balance},
                "$push": {"positions": position}
            }
        )
        
        # Store in trade history
        await self.db.paper_trades.insert_one({
            **position,
            "account_id": account_id,
            "account_name": account["name"]
        })
        
        logger.info(f"Opened {direction} on {symbol} @ ${entry_price} | Leverage: {leverage}x | Margin: ${sizing['margin_required']:.2f} | Liq: ${liq_price:.2f}")
        
        return {
            "success": True,
            "position": position,
            "account_balance": new_balance
        }
    
    async def update_position_price(self, account_id: str, symbol: str, current_price: float) -> Optional[Dict]:
        """Update position with current price and check for liquidation/TP/SL"""
        
        account = await self.get_account(account_id)
        if not account:
            return None
        
        positions = account.get("positions", [])
        updated_positions = []
        closed_position = None
        
        for pos in positions:
            if pos["symbol"] == symbol and pos["status"] == "open":
                pos["current_price"] = current_price
                
                # Calculate unrealized PnL
                if pos["direction"] == "LONG":
                    pnl_pct = ((current_price - pos["entry_price"]) / pos["entry_price"]) * 100 * pos["leverage"]
                else:
                    pnl_pct = ((pos["entry_price"] - current_price) / pos["entry_price"]) * 100 * pos["leverage"]
                
                pos["unrealized_pnl_pct"] = round(pnl_pct, 2)
                pos["unrealized_pnl"] = round(pos["margin"] * (pnl_pct / 100), 2)
                
                # Check liquidation
                if pos["direction"] == "LONG" and current_price <= pos["liquidation_price"]:
                    pos["status"] = "liquidated"
                    pos["exit_price"] = pos["liquidation_price"]
                    pos["realized_pnl"] = -pos["margin"]  # Lose all margin
                    pos["closed_at"] = datetime.now(timezone.utc)
                    closed_position = pos
                    logger.warning(f"LIQUIDATED: {symbol} LONG @ ${pos['liquidation_price']}")
                
                elif pos["direction"] == "SHORT" and current_price >= pos["liquidation_price"]:
                    pos["status"] = "liquidated"
                    pos["exit_price"] = pos["liquidation_price"]
                    pos["realized_pnl"] = -pos["margin"]
                    pos["closed_at"] = datetime.now(timezone.utc)
                    closed_position = pos
                    logger.warning(f"LIQUIDATED: {symbol} SHORT @ ${pos['liquidation_price']}")
                
                # Check stop loss
                elif pos["direction"] == "LONG" and current_price <= pos["stop_loss"]:
                    pos["status"] = "stopped"
                    pos["exit_price"] = pos["stop_loss"]
                    pos["realized_pnl"] = pos["unrealized_pnl"]
                    pos["closed_at"] = datetime.now(timezone.utc)
                    closed_position = pos
                
                elif pos["direction"] == "SHORT" and current_price >= pos["stop_loss"]:
                    pos["status"] = "stopped"
                    pos["exit_price"] = pos["stop_loss"]
                    pos["realized_pnl"] = pos["unrealized_pnl"]
                    pos["closed_at"] = datetime.now(timezone.utc)
                    closed_position = pos
                
                # Check take profit
                elif pos["direction"] == "LONG" and current_price >= pos["take_profit"]:
                    pos["status"] = "profit"
                    pos["exit_price"] = pos["take_profit"]
                    pos["realized_pnl"] = pos["unrealized_pnl"]
                    pos["closed_at"] = datetime.now(timezone.utc)
                    closed_position = pos
                
                elif pos["direction"] == "SHORT" and current_price <= pos["take_profit"]:
                    pos["status"] = "profit"
                    pos["exit_price"] = pos["take_profit"]
                    pos["realized_pnl"] = pos["unrealized_pnl"]
                    pos["closed_at"] = datetime.now(timezone.utc)
                    closed_position = pos
            
            updated_positions.append(pos)
        
        # Update account if position closed
        if closed_position:
            # Remove closed position, update stats
            open_positions = [p for p in updated_positions if p["status"] == "open"]
            
            # Return margin + PnL to balance
            pnl = closed_position.get("realized_pnl", 0)
            margin_return = closed_position["margin"] + pnl
            new_balance = account["balance"] + max(0, margin_return)
            
            # Update stats
            is_win = pnl > 0
            
            await self.db.paper_accounts.update_one(
                {"_id": account_id},
                {
                    "$set": {
                        "balance": new_balance,
                        "positions": open_positions
                    },
                    "$inc": {
                        "total_pnl": pnl,
                        "total_trades": 1,
                        "wins": 1 if is_win else 0,
                        "losses": 0 if is_win else 1
                    }
                }
            )
            
            # Check for auto-reload
            if new_balance < 10:  # Less than $10
                await self.reload_account(account_id)
        else:
            # Just update positions
            await self.db.paper_accounts.update_one(
                {"_id": account_id},
                {"$set": {"positions": updated_positions}}
            )
        
        return closed_position
    
    async def add_margin(self, account_id: str, symbol: str, amount: float) -> Dict:
        """Add margin to an existing position"""
        
        account = await self.get_account(account_id)
        if not account:
            return {"error": "Account not found"}
        
        if amount > account["balance"]:
            return {"error": f"Insufficient balance. Have ${account['balance']:.2f}"}
        
        positions = account.get("positions", [])
        position_found = False
        
        for pos in positions:
            if pos["symbol"] == symbol and pos["status"] == "open":
                position_found = True
                
                # Add margin
                pos["margin"] += amount
                
                # Recalculate liquidation price with new margin
                # More margin = further liquidation price
                effective_leverage = pos["position_size_usd"] / pos["margin"]
                pos["liquidation_price"] = calculate_liquidation_price(
                    entry_price=pos["entry_price"],
                    leverage=int(effective_leverage),
                    direction=pos["direction"],
                    margin_type=pos["margin_type"]
                )
                
                break
        
        if not position_found:
            return {"error": f"No open position for {symbol}"}
        
        # Update account
        new_balance = account["balance"] - amount
        await self.db.paper_accounts.update_one(
            {"_id": account_id},
            {
                "$set": {
                    "balance": new_balance,
                    "positions": positions
                }
            }
        )
        
        return {
            "success": True,
            "added_margin": amount,
            "new_balance": new_balance,
            "new_liq_price": pos["liquidation_price"]
        }
    
    async def close_position(self, account_id: str, symbol: str, exit_price: float) -> Dict:
        """Manually close a position"""
        
        account = await self.get_account(account_id)
        if not account:
            return {"error": "Account not found"}
        
        positions = account.get("positions", [])
        closed_pos = None
        open_positions = []
        
        for pos in positions:
            if pos["symbol"] == symbol and pos["status"] == "open":
                # Calculate final PnL
                if pos["direction"] == "LONG":
                    pnl_pct = ((exit_price - pos["entry_price"]) / pos["entry_price"]) * 100 * pos["leverage"]
                else:
                    pnl_pct = ((pos["entry_price"] - exit_price) / pos["entry_price"]) * 100 * pos["leverage"]
                
                pos["status"] = "closed"
                pos["exit_price"] = exit_price
                pos["realized_pnl"] = round(pos["margin"] * (pnl_pct / 100), 2)
                pos["closed_at"] = datetime.now(timezone.utc)
                closed_pos = pos
            else:
                if pos["status"] == "open":
                    open_positions.append(pos)
        
        if not closed_pos:
            return {"error": f"No open position for {symbol}"}
        
        # Update balance
        pnl = closed_pos["realized_pnl"]
        margin_return = closed_pos["margin"] + pnl
        new_balance = account["balance"] + max(0, margin_return)
        
        is_win = pnl > 0
        
        await self.db.paper_accounts.update_one(
            {"_id": account_id},
            {
                "$set": {
                    "balance": new_balance,
                    "positions": open_positions
                },
                "$inc": {
                    "total_pnl": pnl,
                    "total_trades": 1,
                    "wins": 1 if is_win else 0,
                    "losses": 0 if is_win else 1
                }
            }
        )
        
        return {
            "success": True,
            "position": closed_pos,
            "pnl": pnl,
            "new_balance": new_balance
        }
    
    async def reload_account(self, account_id: str) -> Dict:
        """Reload account to starting balance"""
        
        config = ACCOUNTS.get(account_id)
        if not config:
            return {"error": "Account not found"}
        
        await self.db.paper_accounts.update_one(
            {"_id": account_id},
            {
                "$set": {
                    "balance": config["starting_balance"],
                    "positions": []
                },
                "$inc": {"reloads": 1}
            }
        )
        
        logger.info(f"Reloaded {account_id} to ${config['starting_balance']}")
        
        return {
            "success": True,
            "account": account_id,
            "new_balance": config["starting_balance"]
        }
    
    async def get_account_summary(self, account_id: str) -> Dict:
        """Get detailed account summary"""
        
        account = await self.get_account(account_id)
        if not account:
            return {"error": "Account not found"}
        
        config = ACCOUNTS.get(account_id, {})
        positions = account.get("positions", [])
        open_positions = [p for p in positions if p["status"] == "open"]
        
        # Calculate total unrealized PnL
        total_unrealized = sum(p.get("unrealized_pnl", 0) for p in open_positions)
        total_margin_used = sum(p.get("margin", 0) for p in open_positions)
        
        # Win rate
        total_trades = account.get("total_trades", 0)
        wins = account.get("wins", 0)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        return {
            "account_id": account_id,
            "name": account.get("name"),
            "emoji": config.get("emoji", "💰"),
            "balance": account.get("balance", 0),
            "starting_balance": account.get("starting_balance", 0),
            "available_balance": account.get("balance", 0) - total_margin_used,
            "total_pnl": account.get("total_pnl", 0),
            "unrealized_pnl": total_unrealized,
            "margin_used": total_margin_used,
            "open_positions": len(open_positions),
            "total_trades": total_trades,
            "wins": wins,
            "losses": account.get("losses", 0),
            "win_rate": round(win_rate, 1),
            "reloads": account.get("reloads", 0),
            "positions": open_positions
        }
    
    async def route_signal_to_accounts(
        self,
        signal: Dict,
        engine_name: str = "unknown"
    ) -> List[Dict]:
        """
        Route a trading signal from any engine to BOTH paper accounts
        
        Signal format:
        {
            "symbol": "BTC/USDT",
            "direction": "LONG" or "SHORT",
            "entry_price": 50000.0,
            "stop_loss": 49000.0,
            "take_profit": 52000.0,
            "confidence": 85,
            "confirmations": [...],
            "timeframe": "4h",
            "risk_pct": 2.0  # optional
        }
        """
        results = []
        
        symbol = signal.get("symbol")
        direction = signal.get("direction")
        entry_price = signal.get("entry_price")
        stop_loss = signal.get("stop_loss")
        take_profit = signal.get("take_profit")
        confidence = signal.get("confidence", 80)
        risk_pct = signal.get("risk_pct", 2.0)
        
        if not all([symbol, direction, entry_price, stop_loss, take_profit]):
            logger.warning(f"Invalid signal from {engine_name}: missing required fields")
            return results
        
        # Check if already have position in this symbol
        for acc_id in ["PRO", "STARTER"]:
            account = await self.get_account(acc_id)
            if not account:
                continue
            
            # Check for existing position
            existing = [p for p in account.get("positions", []) 
                       if p["symbol"] == symbol and p["status"] == "open"]
            
            if existing:
                logger.info(f"Already have {symbol} position in {acc_id}, skipping")
                continue
            
            # Adjust risk based on account size
            # PRO can take more risk, Starter is conservative
            if acc_id == "PRO":
                adj_risk = min(risk_pct * 1.5, 5.0)  # Up to 5% risk on PRO
            else:
                adj_risk = min(risk_pct * 0.75, 2.0)  # Max 2% on Starter
            
            # Open position
            result = await self.open_position(
                account_id=acc_id,
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                margin_type="cross",
                risk_pct=adj_risk,
                confidence=confidence,
                signal_data={
                    "engine": engine_name,
                    "confidence": confidence,
                    "confirmations": signal.get("confirmations", []),
                    "timeframe": signal.get("timeframe", "4h"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            
            if "error" not in result:
                pos = result.get("position", {})
                logger.info(f"📊 [{acc_id}] Opened {direction} {symbol} @ ${entry_price:,.2f} | "
                           f"Leverage: {pos.get('leverage')}x | Margin: ${pos.get('margin', 0):,.2f} | "
                           f"Liq: ${pos.get('liquidation_price', 0):,.2f} | Engine: {engine_name}")
                results.append({
                    "account": acc_id,
                    "success": True,
                    "position": pos
                })
            else:
                logger.warning(f"[{acc_id}] Failed to open {symbol}: {result['error']}")
                results.append({
                    "account": acc_id,
                    "success": False,
                    "error": result["error"]
                })
        
        return results
    
    async def update_all_positions(self, price_data: Dict[str, float]) -> List[Dict]:
        """
        Update all positions across all accounts with current prices
        Returns list of any closed positions (liquidated, stopped, profit)
        """
        closed = []
        
        for acc_id in ["PRO", "STARTER"]:
            account = await self.get_account(acc_id)
            if not account:
                continue
            
            for pos in account.get("positions", []):
                if pos["status"] != "open":
                    continue
                
                symbol = pos["symbol"]
                if symbol in price_data:
                    result = await self.update_position_price(acc_id, symbol, price_data[symbol])
                    if result:  # Position was closed
                        closed.append({
                            "account": acc_id,
                            "position": result
                        })
        
        return closed


# Global instance
paper_trading: PaperTradingSystem = None

async def init_paper_trading(db: AsyncIOMotorDatabase) -> PaperTradingSystem:
    global paper_trading
    paper_trading = PaperTradingSystem(db)
    await paper_trading.initialize()
    return paper_trading


async def route_engine_signal(signal: Dict, engine: str) -> List[Dict]:
    """Helper function to route signals from any engine"""
    global paper_trading
    if paper_trading:
        return await paper_trading.route_signal_to_accounts(signal, engine)
    return []
