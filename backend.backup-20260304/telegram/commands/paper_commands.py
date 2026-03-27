"""
Paper Trading Command Handlers
Commands: /accounts, /pro, /starter, /addmargin, /paper
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def handle_accounts(text: str, chat_id: int, context: dict) -> tuple:
    """Handle /accounts command - show both paper trading accounts"""
    from paper_trading import paper_trading
    
    try:
        summary = paper_trading.get_accounts_summary()
        
        response = "📊 PAPER TRADING ACCOUNTS\n\n"
        
        for account_id in ["pro", "starter"]:
            acc = summary.get(account_id, {})
            emoji = "💼" if account_id == "pro" else "🎯"
            name = "PRO ($50K)" if account_id == "pro" else "STARTER ($1.5K)"
            
            balance = acc.get("balance", 0)
            equity = acc.get("equity", balance)
            pnl = acc.get("unrealized_pnl", 0)
            pnl_pct = (pnl / balance * 100) if balance > 0 else 0
            positions = acc.get("open_positions", 0)
            
            pnl_emoji = "🟢" if pnl >= 0 else "🔴"
            
            response += f"""{emoji} {name}
Balance: ${balance:,.2f}
Equity: ${equity:,.2f}
Unrealized PnL: {pnl_emoji} ${pnl:+,.2f} ({pnl_pct:+.2f}%)
Open Positions: {positions}

"""
        
        response += """Commands:
• /pro - View PRO account details
• /starter - View STARTER account details  
• /addmargin <account> <amount> - Add margin
• /paper <symbol> - View position for symbol"""
        
        return response, "paper_trading"
        
    except Exception as e:
        logger.error(f"Error in /accounts: {e}")
        return f"❌ Error loading accounts: {str(e)}", "paper_trading"


async def handle_pro_account(text: str, chat_id: int, context: dict) -> tuple:
    """Handle /pro command - show PRO account details"""
    from paper_trading import paper_trading
    
    try:
        account = paper_trading.get_account("pro")
        positions = paper_trading.get_positions("pro")
        
        balance = account.get("balance", 50000)
        equity = account.get("equity", balance)
        margin_used = account.get("margin_used", 0)
        margin_free = balance - margin_used
        
        response = f"""💼 PRO ACCOUNT ($50K START)

💰 BALANCE
• Balance: ${balance:,.2f}
• Equity: ${equity:,.2f}
• Margin Used: ${margin_used:,.2f}
• Free Margin: ${margin_free:,.2f}

📊 POSITIONS ({len(positions)} open)"""
        
        if positions:
            for pos in positions[:5]:  # Show max 5
                symbol = pos.get("symbol", "").replace("/USDT", "")
                direction = pos.get("direction", "LONG")
                entry = pos.get("entry_price", 0)
                size = pos.get("size_usd", 0)
                pnl = pos.get("unrealized_pnl", 0)
                leverage = pos.get("leverage", 1)
                
                dir_emoji = "🟢" if direction == "LONG" else "🔴"
                pnl_emoji = "+" if pnl >= 0 else ""
                
                response += f"\n{dir_emoji} {symbol} {leverage}x"
                response += f"\n   Entry: ${entry:,.2f} | Size: ${size:,.2f}"
                response += f"\n   PnL: {pnl_emoji}${pnl:,.2f}"
        else:
            response += "\nNo open positions"
        
        response += "\n\n/starter - View starter account"
        
        return response, "paper_trading"
        
    except Exception as e:
        logger.error(f"Error in /pro: {e}")
        return f"❌ Error loading PRO account: {str(e)}", "paper_trading"


async def handle_starter_account(text: str, chat_id: int, context: dict) -> tuple:
    """Handle /starter command - show STARTER account details"""
    from paper_trading import paper_trading
    
    try:
        account = paper_trading.get_account("starter")
        positions = paper_trading.get_positions("starter")
        
        balance = account.get("balance", 1500)
        equity = account.get("equity", balance)
        margin_used = account.get("margin_used", 0)
        margin_free = balance - margin_used
        
        response = f"""🎯 STARTER ACCOUNT ($1.5K START)

💰 BALANCE
• Balance: ${balance:,.2f}
• Equity: ${equity:,.2f}
• Margin Used: ${margin_used:,.2f}
• Free Margin: ${margin_free:,.2f}

📊 POSITIONS ({len(positions)} open)"""
        
        if positions:
            for pos in positions[:5]:  # Show max 5
                symbol = pos.get("symbol", "").replace("/USDT", "")
                direction = pos.get("direction", "LONG")
                entry = pos.get("entry_price", 0)
                size = pos.get("size_usd", 0)
                pnl = pos.get("unrealized_pnl", 0)
                leverage = pos.get("leverage", 1)
                
                dir_emoji = "🟢" if direction == "LONG" else "🔴"
                pnl_emoji = "+" if pnl >= 0 else ""
                
                response += f"\n{dir_emoji} {symbol} {leverage}x"
                response += f"\n   Entry: ${entry:,.2f} | Size: ${size:,.2f}"
                response += f"\n   PnL: {pnl_emoji}${pnl:,.2f}"
        else:
            response += "\nNo open positions"
        
        response += "\n\n/pro - View pro account"
        
        return response, "paper_trading"
        
    except Exception as e:
        logger.error(f"Error in /starter: {e}")
        return f"❌ Error loading STARTER account: {str(e)}", "paper_trading"


async def handle_add_margin(text: str, chat_id: int, context: dict) -> tuple:
    """Handle /addmargin <account> <amount> command"""
    from paper_trading import paper_trading
    
    parts = text.lower().split()
    
    if len(parts) < 3:
        return "Usage: /addmargin <pro|starter> <amount>", "paper_trading"
    
    account_id = parts[1]
    if account_id not in ["pro", "starter"]:
        return "❌ Account must be 'pro' or 'starter'", "paper_trading"
    
    try:
        amount = float(parts[2])
        if amount <= 0:
            return "❌ Amount must be positive", "paper_trading"
        
        result = paper_trading.add_margin(account_id, amount)
        
        if result.get("success"):
            new_balance = result.get("new_balance", 0)
            return f"✅ Added ${amount:,.2f} to {account_id.upper()}\nNew Balance: ${new_balance:,.2f}", "paper_trading"
        else:
            return f"❌ Failed: {result.get('error', 'Unknown error')}", "paper_trading"
            
    except ValueError:
        return "❌ Invalid amount. Use: /addmargin pro 1000", "paper_trading"
    except Exception as e:
        logger.error(f"Error in /addmargin: {e}")
        return f"❌ Error: {str(e)}", "paper_trading"


async def handle_paper_position(text: str, chat_id: int, context: dict) -> tuple:
    """Handle /paper <symbol> command - show position for symbol"""
    from paper_trading import paper_trading
    
    parts = text.lower().split()
    
    if len(parts) < 2:
        return await handle_accounts(text, chat_id, context)
    
    symbol = parts[1].upper()
    if "/" not in symbol:
        symbol = symbol + "/USDT"
    
    try:
        pro_positions = paper_trading.get_positions("pro")
        starter_positions = paper_trading.get_positions("starter")
        
        response = f"📊 PAPER POSITIONS: {symbol}\n\n"
        found = False
        
        # Check PRO account
        for pos in pro_positions:
            if pos.get("symbol") == symbol:
                found = True
                direction = pos.get("direction", "LONG")
                entry = pos.get("entry_price", 0)
                current = pos.get("current_price", entry)
                size = pos.get("size_usd", 0)
                pnl = pos.get("unrealized_pnl", 0)
                leverage = pos.get("leverage", 1)
                liq_price = pos.get("liquidation_price", 0)
                
                dir_emoji = "🟢" if direction == "LONG" else "🔴"
                pnl_emoji = "+" if pnl >= 0 else ""
                
                response += f"""💼 PRO ACCOUNT
{dir_emoji} {direction} {leverage}x
Entry: ${entry:,.2f}
Current: ${current:,.2f}
Size: ${size:,.2f}
PnL: {pnl_emoji}${pnl:,.2f}
Liq Price: ${liq_price:,.2f}

"""
        
        # Check STARTER account
        for pos in starter_positions:
            if pos.get("symbol") == symbol:
                found = True
                direction = pos.get("direction", "LONG")
                entry = pos.get("entry_price", 0)
                current = pos.get("current_price", entry)
                size = pos.get("size_usd", 0)
                pnl = pos.get("unrealized_pnl", 0)
                leverage = pos.get("leverage", 1)
                liq_price = pos.get("liquidation_price", 0)
                
                dir_emoji = "🟢" if direction == "LONG" else "🔴"
                pnl_emoji = "+" if pnl >= 0 else ""
                
                response += f"""🎯 STARTER ACCOUNT
{dir_emoji} {direction} {leverage}x
Entry: ${entry:,.2f}
Current: ${current:,.2f}
Size: ${size:,.2f}
PnL: {pnl_emoji}${pnl:,.2f}
Liq Price: ${liq_price:,.2f}
"""
        
        if not found:
            response = f"No open positions for {symbol} in either account."
        
        return response, "paper_trading"
        
    except Exception as e:
        logger.error(f"Error in /paper: {e}")
        return f"❌ Error: {str(e)}", "paper_trading"


# Export handlers
PAPER_HANDLERS = {
    '/accounts': handle_accounts,
    '/pro': handle_pro_account,
    '/starter': handle_starter_account,
    '/addmargin': handle_add_margin,
    '/paper': handle_paper_position,
}


async def route_paper_command(text: str, chat_id: int, context: dict) -> tuple:
    """Route paper trading commands"""
    text_lower = text.lower().strip()
    
    if text_lower == '/accounts':
        return await handle_accounts(text, chat_id, context)
    elif text_lower == '/pro':
        return await handle_pro_account(text, chat_id, context)
    elif text_lower == '/starter':
        return await handle_starter_account(text, chat_id, context)
    elif text_lower.startswith('/addmargin'):
        return await handle_add_margin(text, chat_id, context)
    elif text_lower.startswith('/paper'):
        return await handle_paper_position(text, chat_id, context)
    
    return None, None
