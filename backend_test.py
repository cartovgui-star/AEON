import requests
import sys
import json
from datetime import datetime

class AeonMarketIntelligenceTester:
    def __init__(self, base_url="https://aeon-chatbot.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}" if not endpoint.startswith('http') else endpoint
        if headers is None:
            headers = {'Content-Type': 'application/json'}

        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)

            success = response.status_code == expected_status
            
            if success:
                try:
                    response_data = response.json()
                    print(f"   Status: {response.status_code}")
                    print(f"   Response: {json.dumps(response_data, indent=2)[:200]}...")
                    self.log_test(name, True)
                    return True, response_data
                except:
                    print(f"   Status: {response.status_code}")
                    print(f"   Response: {response.text[:200]}...")
                    self.log_test(name, True)
                    return True, {}
            else:
                error_msg = f"Expected {expected_status}, got {response.status_code}"
                print(f"   Error: {error_msg}")
                print(f"   Response: {response.text[:200]}...")
                self.log_test(name, False, error_msg)
                return False, {}

        except Exception as e:
            error_msg = f"Request failed: {str(e)}"
            print(f"   Error: {error_msg}")
            self.log_test(name, False, error_msg)
            return False, {}

    def test_root_endpoint(self):
        """Test the root API endpoint"""
        return self.run_test(
            "Root API Endpoint",
            "GET",
            "",
            200
        )

    def test_bot_stats(self):
        """Test bot statistics endpoint"""
        return self.run_test(
            "Bot Statistics",
            "GET", 
            "bot/stats",
            200
        )

    def test_bot_messages(self):
        """Test bot messages endpoint"""
        return self.run_test(
            "Bot Messages History",
            "GET",
            "bot/messages?limit=10",
            200
        )

    def test_bot_test_llm(self):
        """Test LLM connection endpoint"""
        return self.run_test(
            "LLM Connection Test",
            "GET",
            "bot/test",
            200
        )

    def test_webhook_info(self):
        """Test webhook info endpoint"""
        return self.run_test(
            "Webhook Info",
            "GET",
            "bot/webhook-info",
            200
        )

    def test_webhook_post(self):
        """Test webhook POST endpoint with sample Telegram update"""
        sample_update = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "from": {
                    "id": 987654321,
                    "is_bot": False,
                    "first_name": "Test",
                    "username": "testuser"
                },
                "chat": {
                    "id": 987654321,
                    "first_name": "Test",
                    "username": "testuser",
                    "type": "private"
                },
                "date": 1640995200,
                "text": "Hello Aeon, this is a test message"
            }
        }
        
        return self.run_test(
            "Webhook POST Handler",
            "POST",
            "webhook",
            200,
            data=sample_update
        )

    def test_status_endpoints(self):
        """Test status check endpoints"""
        # Test POST status
        success, _ = self.run_test(
            "Create Status Check",
            "POST",
            "status",
            200,
            data={"client_name": "test_client"}
        )
        
        if success:
            # Test GET status
            self.run_test(
                "Get Status Checks",
                "GET",
                "status",
                200
            )

    def test_market_scan_api(self):
        """Test market scan API endpoints"""
        symbols = ['btc', 'eth', 'sol']
        
        for symbol in symbols:
            success, data = self.run_test(
                f"Market Scan - {symbol.upper()}",
                "GET",
                f"market/scan/{symbol}",
                200
            )
            
            if success and data:
                if 'error' in data:
                    self.log_test(f"Market Scan {symbol.upper()} Data", False, f"API error: {data['error']}")
                else:
                    # Verify market scan structure
                    required_fields = ['symbol', 'price', 'technical', 'signals', 'overall_bias']
                    missing_fields = [f for f in required_fields if f not in data]
                    
                    if missing_fields:
                        self.log_test(f"Market Scan {symbol.upper()} Structure", False, f"Missing fields: {missing_fields}")
                    else:
                        self.log_test(f"Market Scan {symbol.upper()} Structure", True, f"Valid market scan data")
                        print(f"   📊 {symbol.upper()}: ${data.get('price', 0):,.2f} | Bias: {data.get('overall_bias', 'N/A')} | Signals: {len(data.get('signals', []))}")
                        
                        # Check technical indicators
                        tech = data.get('technical', {})
                        if tech:
                            indicators = ['rsi', 'macd', 'bb_upper', 'bb_lower', 'ema_9', 'ema_21', 'ema_50']
                            present_indicators = [ind for ind in indicators if ind in tech]
                            if len(present_indicators) >= 5:
                                self.log_test(f"Market Scan {symbol.upper()} Technical Indicators", True, f"Found {len(present_indicators)} indicators")
                            else:
                                self.log_test(f"Market Scan {symbol.upper()} Technical Indicators", False, f"Only {len(present_indicators)} indicators found")

    def test_technical_analysis_api(self):
        """Test technical analysis API endpoints"""
        symbols = ['btc', 'eth', 'sol']
        
        for symbol in symbols:
            success, data = self.run_test(
                f"Technical Analysis - {symbol.upper()}",
                "GET",
                f"market/ta/{symbol}",
                200
            )
            
            if success and data:
                if 'error' in data:
                    self.log_test(f"TA {symbol.upper()} Data", False, f"API error: {data['error']}")
                else:
                    # Verify TA structure
                    required_fields = ['symbol', 'price', 'indicators', 'signals', 'overall_bias']
                    missing_fields = [f for f in required_fields if f not in data]
                    
                    if missing_fields:
                        self.log_test(f"TA {symbol.upper()} Structure", False, f"Missing fields: {missing_fields}")
                    else:
                        self.log_test(f"TA {symbol.upper()} Structure", True, f"Valid TA data")
                        
                        # Check specific indicators
                        indicators = data.get('indicators', {})
                        key_indicators = ['rsi', 'macd', 'macd_signal', 'bb_upper', 'bb_lower', 'ema_9', 'ema_21']
                        present = [ind for ind in key_indicators if ind in indicators]
                        
                        print(f"   📈 {symbol.upper()}: RSI={indicators.get('rsi', 'N/A')} | MACD={indicators.get('macd', 'N/A')} | Bias={data.get('overall_bias', 'N/A')}")
                        
                        if len(present) >= 6:
                            self.log_test(f"TA {symbol.upper()} Indicators Complete", True, f"All key indicators present")
                        else:
                            self.log_test(f"TA {symbol.upper()} Indicators Complete", False, f"Missing indicators: {set(key_indicators) - set(present)}")

    def test_market_positions_api(self):
        """Test market positions API endpoints"""
        symbols = ['btc', 'eth', 'sol']
        
        for symbol in symbols:
            success, data = self.run_test(
                f"Market Positions - {symbol.upper()}",
                "GET",
                f"market/positions/{symbol}",
                200
            )
            
            if success and data:
                if 'error' in data:
                    self.log_test(f"Positions {symbol.upper()} Data", False, f"API error: {data['error']}")
                else:
                    # Verify positions structure
                    required_fields = ['long_short', 'whale', 'taker_flow']
                    missing_fields = [f for f in required_fields if f not in data]
                    
                    if missing_fields:
                        self.log_test(f"Positions {symbol.upper()} Structure", False, f"Missing fields: {missing_fields}")
                    else:
                        self.log_test(f"Positions {symbol.upper()} Structure", True, f"Valid positions data")
                        
                        # Check long/short data
                        ls_data = data.get('long_short', [])
                        whale_data = data.get('whale', [])
                        
                        if ls_data and len(ls_data) > 0:
                            ls_ratio = ls_data[0].get('long_short_ratio', 0)
                            print(f"   📊 {symbol.upper()}: L/S Ratio={ls_ratio:.2f}")
                            self.log_test(f"Positions {symbol.upper()} L/S Data", True, f"L/S ratio: {ls_ratio:.2f}")
                        else:
                            self.log_test(f"Positions {symbol.upper()} L/S Data", False, "No L/S data available")

    def test_market_funding_api(self):
        """Test market funding API endpoints"""
        symbols = ['btc', 'eth', 'sol']
        
        for symbol in symbols:
            success, data = self.run_test(
                f"Market Funding - {symbol.upper()}",
                "GET",
                f"market/funding/{symbol}",
                200
            )
            
            if success and data:
                if 'error' in data:
                    self.log_test(f"Funding {symbol.upper()} Data", False, f"API error: {data['error']}")
                else:
                    # Verify funding structure
                    required_fields = ['funding_rate', 'mark_price']
                    missing_fields = [f for f in required_fields if f not in data]
                    
                    if missing_fields:
                        self.log_test(f"Funding {symbol.upper()} Structure", False, f"Missing fields: {missing_fields}")
                    else:
                        funding_rate = data.get('funding_rate', 0)
                        mark_price = data.get('mark_price', 0)
                        print(f"   💰 {symbol.upper()}: Funding={funding_rate:.6f} | Mark=${mark_price:,.2f}")
                        self.log_test(f"Funding {symbol.upper()} Structure", True, f"Valid funding data")

    def test_learning_system_api(self):
        """Test learning system API endpoints"""
        # Test learning stats
        success, data = self.run_test(
            "Learning System Stats",
            "GET",
            "learning/stats",
            200
        )
        
        if success and data:
            required_fields = ['total_predictions', 'win_rate', 'total_pnl_pct']
            missing_fields = [f for f in required_fields if f not in data]
            
            if missing_fields:
                self.log_test("Learning Stats Structure", False, f"Missing fields: {missing_fields}")
            else:
                total = data.get('total_predictions', 0)
                win_rate = data.get('win_rate', 0)
                pnl = data.get('total_pnl_pct', 0)
                print(f"   🧠 Learning: {total} predictions | {win_rate}% win rate | {pnl:+.2f}% PnL")
                self.log_test("Learning Stats Structure", True, f"Valid learning stats")
        
        # Test open predictions
        success, data = self.run_test(
            "Learning System Open Predictions",
            "GET",
            "learning/open",
            200
        )
        
        if success:
            predictions = data if isinstance(data, list) else []
            self.log_test("Learning Open Predictions", True, f"Found {len(predictions)} open predictions")

    def test_bot_system_connectivity(self):
        """Test bot system connectivity"""
        success, data = self.run_test(
            "Bot System Test",
            "GET",
            "bot/test",
            200
        )
        
        if success and data:
            # Check system connections
            systems = ['llm', 'binance', 'mexc', 'telegram']
            system_status = {}
            
            for system in systems:
                status = data.get(system, False)
                system_status[system] = status
                print(f"   {'✅' if status else '❌'} {system.upper()}: {status}")
            
            # Overall connectivity check
            connected_systems = sum(1 for status in system_status.values() if status)
            total_systems = len(system_status)
            
            if connected_systems >= 3:  # At least 3 systems should be connected
                self.log_test("Bot System Connectivity", True, f"{connected_systems}/{total_systems} systems connected")
            else:
                self.log_test("Bot System Connectivity", False, f"Only {connected_systems}/{total_systems} systems connected")
            
            # Check for users
            users = data.get('users', 0)
            print(f"   👥 Active Users: {users}")

    def test_telegram_market_commands(self):
        """Test Telegram market intelligence commands"""
        commands = [
            ("/scan btc", "Market scan command"),
            ("/ta btc", "Technical analysis command"),
            ("/positions btc", "Positions command"),
            ("/funding btc", "Funding command"),
            ("btc price analysis", "Trading keyword detection")
        ]
        
        for command, description in commands:
            sample_update = {
                "update_id": 123456789,
                "message": {
                    "message_id": 1,
                    "from": {
                        "id": 987654321,
                        "is_bot": False,
                        "first_name": "Test",
                        "username": "testuser"
                    },
                    "chat": {
                        "id": 987654321,
                        "first_name": "Test",
                        "username": "testuser",
                        "type": "private"
                    },
                    "date": 1640995200,
                    "text": command
                }
            }
            
            success, response = self.run_test(
                f"Telegram Command - {command}",
                "POST",
                "webhook",
                200,
                data=sample_update
            )
            
            if success:
                self.log_test(f"{description}", True, f"Command processed successfully")

    def test_mexc_integration(self):
        """Test MEXC integration endpoints"""
        success, data = self.run_test(
            "MEXC Live Data",
            "GET",
            "mexc/live",
            200
        )
        
        if success and data:
            if 'error' in data:
                self.log_test("MEXC Integration", False, f"MEXC API error: {data['error']}")
            else:
                # Check for expected crypto pairs
                expected_symbols = ['BTC', 'ETH', 'SOL']
                found_symbols = list(data.keys())
                missing_symbols = [s for s in expected_symbols if s not in found_symbols]
                
                if missing_symbols:
                    self.log_test("MEXC Data Coverage", False, f"Missing symbols: {missing_symbols}")
                else:
                    self.log_test("MEXC Data Coverage", True, f"All expected symbols present")
                    
                    # Verify orderbook data structure
                    valid_structure = True
                    for symbol, info in data.items():
                        required_fields = ['price', 'change', 'bid_depth', 'ask_depth', 'imbalance']
                        missing_fields = [f for f in required_fields if f not in info]
                        if missing_fields:
                            valid_structure = False
                            break
                        else:
                            price = info.get('price', 'N/A')
                            change = info.get('change', 'N/A')
                            imbalance = info.get('imbalance', 'N/A')
                            print(f"   📊 {symbol}: {price} ({change}) | Imbalance: {imbalance}")
                    
                    if valid_structure:
                        self.log_test("MEXC Orderbook Structure", True, "Valid orderbook data for all symbols")
                    else:
                        self.log_test("MEXC Orderbook Structure", False, "Invalid orderbook data structure")

    def test_bot_test_mexc_connection(self):
        """Test bot test endpoint specifically for MEXC connection"""
        success, data = self.run_test(
            "Bot Test - MEXC Connection",
            "GET",
            "bot/test",
            200
        )
        
        if success and data:
            # Check MEXC connection status
            mexc_connected = data.get('mexc_connected', False)
            if mexc_connected:
                self.log_test("MEXC Connection Status", True, "MEXC is connected")
                print(f"   ✅ MEXC Connected: {mexc_connected}")
                
                # Check if sample MEXC data is present
                if 'mexc_sample' in data and data['mexc_sample']:
                    self.log_test("MEXC Sample Data", True, "Sample data available")
                    print(f"   📊 Sample MEXC data present")
                else:
                    self.log_test("MEXC Sample Data", False, "No sample data in test response")
            else:
                self.log_test("MEXC Connection Status", False, "MEXC is not connected")
                print(f"   ❌ MEXC Connected: {mexc_connected}")
                
                # Check for error details
                if 'error' in data:
                    print(f"   Error details: {data['error']}")
            
            # Also verify other connections
            llm_connected = data.get('llm_connected', False)
            telegram_token_set = data.get('telegram_token_set', False)
            
            print(f"   🤖 LLM Connected: {llm_connected}")
            print(f"   📱 Telegram Token Set: {telegram_token_set}")
            
            if data.get('sample_response'):
                print(f"   💬 Sample Response: {data['sample_response'][:100]}...")
        
        return success, data

    def test_mexc_orderbook_endpoint(self):
        """Test specific MEXC orderbook endpoint"""
        symbols = ['BTC', 'ETH', 'SOL']
        
        for symbol in symbols:
            success, data = self.run_test(
                f"MEXC Orderbook - {symbol}",
                "GET",
                f"mexc/orderbook/{symbol}",
                200
            )
            
            if success and data:
                if 'error' in data:
                    self.log_test(f"MEXC {symbol} Orderbook Structure", False, f"API error: {data['error']}")
                else:
                    # Verify orderbook structure
                    required_fields = ['symbol', 'bid_depth', 'ask_depth', 'imbalance', 'top_bid', 'top_ask', 'timestamp']
                    missing_fields = [f for f in required_fields if f not in data]
                    
                    if missing_fields:
                        self.log_test(f"MEXC {symbol} Orderbook Structure", False, f"Missing fields: {missing_fields}")
                    else:
                        self.log_test(f"MEXC {symbol} Orderbook Structure", True, f"Valid orderbook structure")
                        print(f"   📊 {symbol} Orderbook: Bids={data['bid_depth']}, Asks={data['ask_depth']}, Imbalance={data['imbalance']}")

    def test_alchemical_questions(self):
        """Test alchemical questions endpoint"""
        success, data = self.run_test(
            "Alchemical Questions Bank",
            "GET",
            "bot/questions",
            200
        )
        
        if success and data:
            questions = data.get('questions', [])
            count = data.get('count', 0)
            
            if count >= 30:  # Should have 30 questions as mentioned in requirements
                self.log_test("Alchemical Questions Count", True, f"Found {count} questions")
                print(f"   🔮 Question bank contains {count} alchemical questions")
                
                # Verify some questions contain expected alchemical/masonic terms
                alchemical_terms = ['alchemy', 'masonic', 'transmutation', 'prima materia', 'great work', 'rubedo', 'nigredo', 'albedo']
                questions_text = ' '.join(questions).lower()
                found_terms = [term for term in alchemical_terms if term in questions_text]
                
                if len(found_terms) >= 3:  # Should contain several alchemical terms
                    self.log_test("Alchemical Questions Content", True, f"Contains alchemical terms: {found_terms[:3]}")
                else:
                    self.log_test("Alchemical Questions Content", False, f"Missing alchemical terminology")
                    
            else:
                self.log_test("Alchemical Questions Count", False, f"Expected 30+ questions, got {count}")

    def test_telegram_commands(self):
        """Test Telegram webhook with specific commands"""
        commands = [
            ("/start", "start"),
            ("/price", "trading"), 
            ("/probe", "alchemy"),
            ("/ritual", "ritual")
        ]
        
        for command, expected_context in commands:
            sample_update = {
                "update_id": 123456789,
                "message": {
                    "message_id": 1,
                    "from": {
                        "id": 987654321,
                        "is_bot": False,
                        "first_name": "Test",
                        "username": "testuser"
                    },
                    "chat": {
                        "id": 987654321,
                        "first_name": "Test", 
                        "username": "testuser",
                        "type": "private"
                    },
                    "date": 1640995200,
                    "text": command
                }
            }
            
            success, response = self.run_test(
                f"Telegram Command - {command}",
                "POST",
                "webhook",
                200,
                data=sample_update
            )
            
            if success:
                self.log_test(f"Command {command} Response", True, f"Command processed successfully")

        # Test trading mode detection
        trading_message = {
            "update_id": 123456790,
            "message": {
                "message_id": 2,
                "from": {"id": 987654321, "is_bot": False, "first_name": "Test", "username": "testuser"},
                "chat": {"id": 987654321, "first_name": "Test", "username": "testuser", "type": "private"},
                "date": 1640995200,
                "text": "What's the BTC price and volume looking like?"
            }
        }
        
        success, response = self.run_test(
            "Trading Mode Detection",
            "POST", 
            "webhook",
            200,
            data=trading_message
        )
        
        if success:
            self.log_test("Trading Mode Detection", True, "Trading keywords detected")

        # Test alchemy mode detection  
        alchemy_message = {
            "update_id": 123456791,
            "message": {
                "message_id": 3,
                "from": {"id": 987654321, "is_bot": False, "first_name": "Test", "username": "testuser"},
                "chat": {"id": 987654321, "first_name": "Test", "username": "testuser", "type": "private"},
                "date": 1640995200,
                "text": "What is the nature of consciousness and reality?"
            }
        }
        
        success, response = self.run_test(
            "Alchemy Mode Detection",
            "POST",
            "webhook", 
            200,
            data=alchemy_message
        )
        
        if success:
            self.log_test("Alchemy Mode Detection", True, "Philosophical message processed")

    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting Aeon Bot API Tests (MEXC Integration)")
        print("=" * 50)
        
        # Test all endpoints
        self.test_root_endpoint()
        self.test_bot_stats()
        self.test_bot_messages()
        self.test_bot_test_llm()
        self.test_webhook_info()
        self.test_status_endpoints()
        
        # NEW: Test MEXC-specific endpoints
        print("\n🔥 Testing MEXC Integration...")
        self.test_mexc_live_endpoint()
        self.test_mexc_orderbook_endpoint()
        self.test_bot_test_mexc_connection()
        
        # NEW: Test Aeon-specific endpoints
        print("\n🔮 Testing Aeon Quartet Features...")
        self.test_alchemical_questions()
        self.test_telegram_commands()
        
        self.test_webhook_post()
        
        # Print summary
        print("\n" + "=" * 50)
        print(f"📊 Test Summary: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            print("⚠️  Some tests failed. Check the details above.")
            return 1

    def get_test_results(self):
        """Return detailed test results"""
        return {
            "total_tests": self.tests_run,
            "passed_tests": self.tests_passed,
            "success_rate": (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0,
            "results": self.test_results
        }

def main():
    tester = AeonBotAPITester()
    exit_code = tester.run_all_tests()
    
    # Save detailed results
    results = tester.get_test_results()
    with open('/app/backend_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: /app/backend_test_results.json")
    return exit_code

if __name__ == "__main__":
    sys.exit(main())