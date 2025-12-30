#!/usr/bin/env python3
"""
Website Stress Test Script

This script uses Python to perform a stress test on a website by simulating
concurrent connections and measuring response times and error rates.

Requirements:
    pip install aiohttp click tqdm

Usage:
    # Basic test
    python stress_test.py --url https://example.com --users 50 --duration 30

    # With ramp-up and custom settings
    python stress_test.py --url https://api.example.com --users 100 --duration 60 --ramp-up 10 --delay 500 --output results.json

    # POST request with headers and body
    python stress_test.py --url https://api.example.com/endpoint --method POST --headers '{"Content-Type": "application/json"}' --body '{"test": true}'
"""

import asyncio
import time
import json
import argparse
from datetime import datetime
from collections import defaultdict
import signal
import sys

try:
    import aiohttp
    from tqdm import tqdm
except ImportError:
    print("Required packages not installed. Please run:")
    print("pip install aiohttp tqdm")
    sys.exit(1)


class StressTest:
    def __init__(self, options):
        self.options = options
        self.results = {
            "url": options.url,
            "testConfig": {
                "users": options.users,
                "duration": options.duration,
                "rampUp": options.ramp_up,
                "delay": options.delay,
                "timeout": options.timeout,
                "method": options.method,
            },
            "startTime": None,
            "endTime": None,
            "totalRequests": 0,
            "successfulRequests": 0,
            "failedRequests": 0,
            "responseTimesMs": [],
            "statusCodes": defaultdict(int),
            "errors": defaultdict(int),
        }
        self.is_running = True
        self.active_users = 0
        self.progress_bar = None
        self.session = None

    def get_user_count(self, elapsed_time):
        """Calculate how many users should be active based on ramp-up time"""
        if not self.options.ramp_up or self.options.ramp_up <= 0:
            return self.options.users
        
        ramp_up_percent = min(elapsed_time / self.options.ramp_up, 1)
        return int(self.options.users * ramp_up_percent)

    async def make_request(self, user_id):
        """Make a single HTTP request and record the results"""
        try:
            start_time = time.time()
            
            headers = json.loads(self.options.headers)
            
            request_kwargs = {
                "timeout": aiohttp.ClientTimeout(total=self.options.timeout / 1000),
                "headers": headers,
            }
            
            if self.options.body and self.options.method.upper() in ["POST", "PUT", "PATCH"]:
                request_kwargs["data"] = self.options.body
            
            async with self.session.request(
                self.options.method,
                self.options.url,
                **request_kwargs
            ) as response:
                await response.read()
                
                end_time = time.time()
                response_time = (end_time - start_time) * 1000  # Convert to ms
                
                self.results["totalRequests"] += 1
                self.results["successfulRequests"] += 1
                self.results["responseTimesMs"].append(response_time)
                self.results["statusCodes"][response.status] += 1
                
                if self.progress_bar:
                    self.progress_bar.update(1)
                
                return response_time
                
        except asyncio.TimeoutError:
            self.results["totalRequests"] += 1
            self.results["failedRequests"] += 1
            self.results["errors"]["Timeout"] += 1
            
            if self.progress_bar:
                self.progress_bar.update(1)
            
            return None
            
        except aiohttp.ClientError as e:
            self.results["totalRequests"] += 1
            self.results["failedRequests"] += 1
            
            if hasattr(e, 'status'):
                self.results["statusCodes"][e.status] += 1
                error_key = f"HTTP {e.status}"
            else:
                error_key = "Connection Error"
            
            self.results["errors"][error_key] += 1
            
            if self.progress_bar:
                self.progress_bar.update(1)
            
            return None
            
        except Exception as e:
            self.results["totalRequests"] += 1
            self.results["failedRequests"] += 1
            self.results["errors"]["Unknown Error"] += 1
            
            if self.progress_bar:
                self.progress_bar.update(1)
            
            return None

    async def simulate_user(self, user_id):
        """Simulate a single user making requests"""
        while self.is_running:
            await self.make_request(user_id)
            
            if self.options.delay > 0:
                await asyncio.sleep(self.options.delay / 1000)

    async def run_test(self):
        """Run the stress test"""
        print(f"\nStarting stress test for {self.options.url}")
        print(f"Simulating up to {self.options.users} concurrent users for {self.options.duration} seconds")
        if self.options.ramp_up > 0:
            print(f"Gradually ramping up users over {self.options.ramp_up} seconds")
        print("\n")
        
        self.results["startTime"] = datetime.now()
        
        self.session = aiohttp.ClientSession()
        
        estimated_requests = self.options.users * self.options.duration
        self.progress_bar = tqdm(
            total=estimated_requests,
            desc="Requests",
            unit="req",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"
        )
        
        user_tasks = []
        
        async def duration_timer():
            start = time.time()
            while self.is_running:
                elapsed = time.time() - start
                if elapsed >= self.options.duration:
                    await self.stop_test()
                    break
                await asyncio.sleep(0.1)
        
        timer_task = asyncio.create_task(duration_timer())
        
        start_time = time.time()
        while self.is_running and self.active_users < self.options.users:
            elapsed = time.time() - start_time
            target_users = self.get_user_count(elapsed)
            
            while self.active_users < target_users and self.active_users < self.options.users:
                self.active_users += 1
                task = asyncio.create_task(self.simulate_user(self.active_users))
                user_tasks.append(task)
            
            if self.active_users >= self.options.users:
                break
            
            await asyncio.sleep(0.1)
        
        await timer_task
        
        for task in user_tasks:
            task.cancel()
        
        await asyncio.gather(*user_tasks, return_exceptions=True)
        
        await self.session.close()
        
        if self.progress_bar:
            self.progress_bar.close()

    async def stop_test(self):
        """Stop the test and print results"""
        self.is_running = False
        self.results["endTime"] = datetime.now()
        
        await asyncio.sleep(1)
        
        total_duration = (self.results["endTime"] - self.results["startTime"]).total_seconds()
        total_duration_ms = total_duration * 1000
        
        response_times = self.results["responseTimesMs"]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        sorted_response_times = sorted(response_times)
        median_response_time = sorted_response_times[len(sorted_response_times) // 2] if sorted_response_times else 0
        p95_response_time = sorted_response_times[int(len(sorted_response_times) * 0.95)] if sorted_response_times else 0
        
        requests_per_second = self.results["totalRequests"] / total_duration if total_duration > 0 else 0
        success_rate = (self.results["successfulRequests"] / self.results["totalRequests"] * 100) if self.results["totalRequests"] > 0 else 0
        
        self.results["metrics"] = {
            "totalDurationMs": total_duration_ms,
            "avgResponseTimeMs": avg_response_time,
            "medianResponseTimeMs": median_response_time,
            "p95ResponseTimeMs": p95_response_time,
            "requestsPerSecond": requests_per_second,
            "successRate": success_rate,
        }
        
        print("\n\n========== TEST RESULTS ==========")
        print(f"URL: {self.results['url']}")
        print(f"Duration: {total_duration:.2f} seconds")
        print(f"Concurrent Users: {self.options.users}")
        print(f"Total Requests: {self.results['totalRequests']}")
        print(f"Successful Requests: {self.results['successfulRequests']} ({success_rate:.2f}%)")
        print(f"Failed Requests: {self.results['failedRequests']}")
        print(f"Requests Per Second: {requests_per_second:.2f}")
        print("\nResponse Times:")
        print(f"  Average: {avg_response_time:.2f} ms")
        print(f"  Median: {median_response_time:.0f} ms")
        print(f"  95th Percentile: {p95_response_time:.0f} ms")
        
        print("\nStatus Code Distribution:")
        for code in sorted(self.results["statusCodes"].keys()):
            count = self.results["statusCodes"][code]
            percentage = (count / self.results["totalRequests"] * 100) if self.results["totalRequests"] > 0 else 0
            print(f"  {code}: {count} ({percentage:.2f}%)")
        
        if self.results["errors"]:
            print("\nError Distribution:")
            sorted_errors = sorted(self.results["errors"].items(), key=lambda x: x[1], reverse=True)
            for error, count in sorted_errors:
                percentage = (count / self.results["totalRequests"] * 100) if self.results["totalRequests"] > 0 else 0
                print(f"  {error}: {count} ({percentage:.2f}%)")
        
        if self.options.output:
            output_results = {
                **self.results,
                "statusCodes": dict(self.results["statusCodes"]),
                "errors": dict(self.results["errors"]),
                "startTime": self.results["startTime"].isoformat(),
                "endTime": self.results["endTime"].isoformat(),
            }
            
            with open(self.options.output, 'w') as f:
                json.dump(output_results, f, indent=2)
            print(f"\nDetailed results saved to {self.options.output}")


def main():
    parser = argparse.ArgumentParser(description="Website Stress Test Script")
    parser.add_argument("--url", required=True, help="Target URL to stress test")
    parser.add_argument("--users", type=int, default=10, help="Number of concurrent users (default: 10)")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds (default: 60)")
    parser.add_argument("--ramp-up", type=int, default=0, dest="ramp_up",
                        help="Gradually ramp up users over this many seconds (default: 0)")
    parser.add_argument("--delay", type=int, default=1000,
                        help="Delay between requests for each user in milliseconds (default: 1000)")
    parser.add_argument("--timeout", type=int, default=5000,
                        help="Request timeout in milliseconds (default: 5000)")
    parser.add_argument("--output", help="Save results to JSON file")
    parser.add_argument("--method", default="GET", help="HTTP method (GET, POST, etc.) (default: GET)")
    parser.add_argument("--headers", default="{}", help='HTTP headers in JSON format (default: "{}")')
    parser.add_argument("--body", default="", help="Request body for POST/PUT requests")
    
    args = parser.parse_args()
    
    stress_test = StressTest(args)
    
    def signal_handler(sig, frame):
        print("\nTest interrupted by user")
        asyncio.create_task(stress_test.stop_test())
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        asyncio.run(stress_test.run_test())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
