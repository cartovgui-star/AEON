"""
Tests for autonomous trader position sizing and leverage
"""

import pytest
import sys
sys.path.insert(0, '/app/backend')


class TestPositionSizing:
    """Test dynamic position sizing calculations"""
    
    def test_position_size_low_confidence(self):
        """Low confidence should give smaller position"""
        from autonomous_trader_v2 import AutonomousTraderV2
        trader = AutonomousTraderV2(db=None)
        
        size = trader.calculate_position_size(60, 2)  # 60% conf, 2% pct
        assert size >= 500
        assert size <= 1000  # Should be on lower end
    
    def test_position_size_high_confidence(self):
        """High confidence should give larger position"""
        from autonomous_trader_v2 import AutonomousTraderV2
        trader = AutonomousTraderV2(db=None)
        
        size = trader.calculate_position_size(90, 5)  # 90% conf, 5% pct
        assert size >= 1000
        assert size <= 2500  # Should be on higher end
    
    def test_position_size_bounds(self):
        """Position size should stay within bounds"""
        from autonomous_trader_v2 import AutonomousTraderV2
        trader = AutonomousTraderV2(db=None)
        
        # Very low should hit minimum
        size_min = trader.calculate_position_size(50, 1)
        assert size_min >= 500
        
        # Very high should hit maximum
        size_max = trader.calculate_position_size(95, 10)
        assert size_max <= 2500
    
    def test_position_size_rounds_to_50(self):
        """Position size should round to nearest 50"""
        from autonomous_trader_v2 import AutonomousTraderV2
        trader = AutonomousTraderV2(db=None)
        
        size = trader.calculate_position_size(75, 3)
        assert size % 50 == 0


class TestLeverage:
    """Test leverage calculations"""
    
    def test_leverage_scalp_style(self):
        """SCALP style should have higher leverage"""
        from autonomous_trader_v2 import AutonomousTraderV2
        trader = AutonomousTraderV2(db=None)
        trader.dynamic_leverage = True
        
        lev = trader.calculate_leverage(80, trade_style="SCALP")
        assert lev >= 50
        assert lev <= 200
    
    def test_leverage_swing_style(self):
        """SWING style should have lower leverage"""
        from autonomous_trader_v2 import AutonomousTraderV2
        trader = AutonomousTraderV2(db=None)
        trader.dynamic_leverage = True
        
        lev = trader.calculate_leverage(80, trade_style="SWING")
        assert lev >= 10
        assert lev <= 25
    
    def test_leverage_volatile_market(self):
        """VOLATILE market should increase leverage"""
        from autonomous_trader_v2 import AutonomousTraderV2
        trader = AutonomousTraderV2(db=None)
        trader.dynamic_leverage = True
        
        lev_normal = trader.calculate_leverage(80, market_regime="RANGING", trade_style="DAY")
        lev_volatile = trader.calculate_leverage(80, market_regime="VOLATILE", trade_style="DAY")
        
        assert lev_volatile >= lev_normal


class TestTradeStyles:
    """Test trade style determination"""
    
    def test_scalp_from_short_timeframe(self):
        """Short timeframes should produce SCALP"""
        from autonomous_trader_v2 import AutonomousTraderV2
        trader = AutonomousTraderV2(db=None)
        
        style = trader.determine_trade_style("15m", 70)
        assert style == "SCALP"
    
    def test_swing_from_daily(self):
        """Daily timeframe should produce SWING"""
        from autonomous_trader_v2 import AutonomousTraderV2
        trader = AutonomousTraderV2(db=None)
        
        style = trader.determine_trade_style("1d", 70)
        assert style == "SWING"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
