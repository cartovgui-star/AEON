import requests
import sys
import json
from datetime import datetime

class AeonBotAPITester:
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

    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting Aeon Bot API Tests")
        print("=" * 50)
        
        # Test all endpoints
        self.test_root_endpoint()
        self.test_bot_stats()
        self.test_bot_messages()
        self.test_bot_test_llm()
        self.test_webhook_info()
        self.test_status_endpoints()
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