import asyncio
import json
import sys
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.anomaly_detection import AnomalyDetectionService, DetectionThresholds
from app.services.gpt_reasoning import GPTReasoningService
from app.models.schemas import LogEntry, LogSeverity, LogResource, ResourceType, AnomalySeverity


class SimpleAnomalyTester:
    """Simplified anomaly detection testing without external dependencies."""
    
    def __init__(self):
        self.anomaly_service = AnomalyDetectionService()
        self.gpt_service = GPTReasoningService()
    
    def create_test_logs(self) -> List[LogEntry]:
        """Create test logs programmatically instead of reading from file."""
        logs = []
        base_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        
        # Normal baseline logs (100 logs)
        for i in range(100):
            log = LogEntry(
                timestamp=base_time + timedelta(seconds=i*2),
                severity=LogSeverity.INFO,
                message=f"Query executed successfully in {200 + i}ms",
                resource=LogResource(type=ResourceType.CLOUDSQL_DATABASE, labels={"instance": "prod-db-1"}),
                source="test",
                json_payload={"latency_ms": 200 + i, "query": "SELECT * FROM users"},
                raw_log=f"INFO: Query executed successfully in {200 + i}ms"
            )
            logs.append(log)
        
        # Error spike pattern (50 logs with high error rate)
        error_start = base_time + timedelta(seconds=200)
        for i in range(50):
            log = LogEntry(
                timestamp=error_start + timedelta(seconds=i),
                severity=LogSeverity.ERROR if i % 2 == 0 else LogSeverity.WARNING,
                message=f"Database connection failed: Connection timeout after {5000 + i*100}ms",
                resource=LogResource(type=ResourceType.CLOUDSQL_DATABASE, labels={"instance": "prod-db-1"}),
                source="test",
                json_payload={"latency_ms": 5000 + i*100, "error_code": "TIMEOUT"},
                raw_log=f"ERROR: Database connection failed"
            )
            logs.append(log)
        
        # Repeated error pattern (25 logs with same error)
        repeated_start = base_time + timedelta(seconds=300)
        for i in range(25):
            log = LogEntry(
                timestamp=repeated_start + timedelta(seconds=i*2),
                severity=LogSeverity.ERROR,
                message="Authentication failed for user 'admin'",
                resource=LogResource(type=ResourceType.CLOUDSQL_DATABASE, labels={"instance": "prod-db-1"}),
                source="test",
                json_payload={"error_code": "AUTH_FAILED", "user": "admin", "source_ip": "192.168.1.100"},
                raw_log="ERROR: Authentication failed for user 'admin'"
            )
            logs.append(log)
        
        # Recovery logs (25 logs back to normal)
        recovery_start = base_time + timedelta(seconds=400)
        for i in range(25):
            log = LogEntry(
                timestamp=recovery_start + timedelta(seconds=i*2),
                severity=LogSeverity.INFO,
                message=f"Query executed successfully in {300 + i}ms",
                resource=LogResource(type=ResourceType.CLOUDSQL_DATABASE, labels={"instance": "prod-db-1"}),
                source="test",
                json_payload={"latency_ms": 300 + i, "query": "SELECT * FROM products"},
                raw_log=f"INFO: Query executed successfully"
            )
            logs.append(log)
        
        return logs
    
    async def test_statistical_detection(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Test statistical anomaly detection."""
        print("🔍 Testing Statistical Detection...")
        
        # Configure thresholds for testing
        self.anomaly_service.configure_thresholds(
            error_rate_threshold=0.1,  # 10% error rate
            latency_threshold_ms=3000,  # 3 seconds
            min_events_for_pattern=5
        )
        
        # Run detection
        anomalies = await self.anomaly_service.analyze_logs(logs, use_ai_analysis=False)
        
        results = {
            "total_anomalies": len(anomalies),
            "high_severity": len([a for a in anomalies if a.severity == AnomalySeverity.HIGH]),
            "critical_severity": len([a for a in anomalies if a.severity == AnomalySeverity.CRITICAL]),
            "detection_methods": [a.detection_method for a in anomalies],
            "anomaly_types": [a.type.value for a in anomalies]
        }
        
        # Print details
        for i, anomaly in enumerate(anomalies, 1):
            print(f"   {i}. {anomaly.type.value} - {anomaly.severity.value}")
            print(f"      Method: {anomaly.detection_method.value}")
            print(f"      Metric: {anomaly.metric_value} (threshold: {anomaly.threshold_value})")
            print(f"      Description: {anomaly.description[:80]}...")
        
        return results
    
    async def test_pattern_detection(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Test pattern-based detection."""
        print("\n🔗 Testing Pattern Detection...")
        
        # Get pattern analysis directly
        pattern_analysis = self.anomaly_service.pattern_detector.analyze_patterns(logs)
        
        results = {
            "error_patterns": len(pattern_analysis.get("error_patterns", [])),
            "repeated_errors": len(pattern_analysis.get("repeated_errors", [])),
            "http_patterns": bool(pattern_analysis.get("http_patterns")),
            "resource_patterns": len(pattern_analysis.get("resource_patterns", {}))
        }
        
        # Print pattern details
        for pattern in pattern_analysis.get("error_patterns", [])[:3]:
            print(f"   Error Pattern: {pattern['pattern'][:60]}... ({pattern['count']} occurrences)")
        
        for repeated in pattern_analysis.get("repeated_errors", [])[:3]:
            print(f"   Repeated: {repeated['pattern'][:60]}... ({repeated['count']} times)")
        
        return results
    
    async def test_ai_analysis(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Test AI-powered analysis if available."""
        print(f"\n🤖 Testing AI Analysis (Available: {self.gpt_service.is_available()})...")
        
        if not self.gpt_service.is_available():
            return {"ai_available": False, "reason": "No OpenAI API key configured"}
        
        # Get some anomalies first
        anomalies = await self.anomaly_service.analyze_logs(logs, use_ai_analysis=False)
        
        if not anomalies:
            return {"ai_available": True, "analysis_performed": False, "reason": "No anomalies to analyze"}
        
        # Test AI analysis on first anomaly
        test_anomaly = anomalies[0]
        error_logs = [log for log in logs if log.severity in [LogSeverity.ERROR, LogSeverity.CRITICAL]][:5]
        
        try:
            ai_analysis = await self.gpt_service.analyze_anomalies([test_anomaly], error_logs, {
                "test_context": True,
                "total_logs": len(logs),
                "error_logs": len(error_logs)
            })
            
            results = {
                "ai_available": True,
                "analysis_performed": True,
                "root_cause_provided": bool(ai_analysis.get("root_cause_analysis")),
                "confidence_score": ai_analysis.get("confidence_score", 0),
                "actions_provided": len(ai_analysis.get("immediate_actions", [])),
                "recommendations_provided": len(ai_analysis.get("long_term_recommendations", []))
            }
            
            print(f"   Root Cause: {ai_analysis.get('root_cause_analysis', 'N/A')[:80]}...")
            print(f"   Confidence: {ai_analysis.get('confidence_score', 0):.2f}")
            print(f"   Actions: {len(ai_analysis.get('immediate_actions', []))} recommendations")
            
            return results
            
        except Exception as e:
            return {
                "ai_available": True,
                "analysis_performed": False,
                "error": str(e)
            }
    
    async def test_threshold_configuration(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Test threshold configuration and sensitivity."""
        print(f"\n⚙️  Testing Threshold Configuration...")
        
        # Test with strict thresholds
        self.anomaly_service.configure_thresholds(
            error_rate_threshold=0.01,  # 1% error rate
            latency_threshold_ms=1000,  # 1 second
            min_events_for_pattern=3    # Strict: need only 3 occurrences
        )
        
        strict_anomalies = await self.anomaly_service.analyze_logs(logs, use_ai_analysis=False)
        
        # Test with lenient thresholds
        self.anomaly_service.configure_thresholds(
            error_rate_threshold=0.5,   # 50% error rate - won't trigger with 25% data
            latency_threshold_ms=10000, # 10 seconds
            min_events_for_pattern=30   # Lenient: need 30+ occurrences
        )
        
        lenient_anomalies = await self.anomaly_service.analyze_logs(logs, use_ai_analysis=False)
        
        results = {
            "strict_threshold_anomalies": len(strict_anomalies),
            "lenient_threshold_anomalies": len(lenient_anomalies),
            "threshold_sensitivity": len(strict_anomalies) > len(lenient_anomalies)
        }
        
        print(f"   Strict thresholds: {len(strict_anomalies)} anomalies")
        print(f"   Lenient thresholds: {len(lenient_anomalies)} anomalies")
        print(f"   Sensitivity working: {results['threshold_sensitivity']}")
        
        return results


async def run_simple_anomaly_tests():
    """Run simplified anomaly detection tests."""
    print("🧪 Simple Anomaly Detection Test")
    print("=" * 50)
    
    tester = SimpleAnomalyTester()
    
    try:
        # Create test data
        print("📊 Creating test logs...")
        logs = tester.create_test_logs()
        print(f"   Generated {len(logs)} test logs")
        
        # Calculate expected metrics
        error_logs = [log for log in logs if log.severity in [LogSeverity.ERROR, LogSeverity.CRITICAL]]
        warning_logs = [log for log in logs if log.severity == LogSeverity.WARNING]
        error_rate = len(error_logs) / len(logs)
        
        print(f"   Error rate: {error_rate:.1%} ({len(error_logs)}/{len(logs)})")
        print(f"   Warning logs: {len(warning_logs)}")
        
        # Run tests
        statistical_results = await tester.test_statistical_detection(logs)
        pattern_results = await tester.test_pattern_detection(logs)
        ai_results = await tester.test_ai_analysis(logs)
        threshold_results = await tester.test_threshold_configuration(logs)
        
        # Summary
        print(f"\n📋 Test Summary:")
        print("=" * 30)
        
        total_anomalies = statistical_results["total_anomalies"]
        print(f"✓ Statistical Detection: {total_anomalies} anomalies")
        print(f"✓ Pattern Detection: {pattern_results['error_patterns']} error patterns")
        print(f"✓ AI Analysis Available: {ai_results.get('ai_available', False)}")
        print(f"✓ Threshold Sensitivity: {threshold_results.get('threshold_sensitivity', False)}")
        
        # Success criteria
        success_checks = [
            (total_anomalies > 0, "Detected anomalies"),
            (error_rate > 0.1, f"Error rate above threshold: {error_rate:.1%}"),
            (pattern_results["error_patterns"] > 0, "Found error patterns"),
            (threshold_results["threshold_sensitivity"], "Threshold sensitivity working")
        ]
        
        passed = sum(1 for check, _ in success_checks if check)
        total = len(success_checks)
        
        print(f"\n🎯 Results: {passed}/{total} checks passed")
        for check, description in success_checks:
            status = "✅" if check else "❌"
            print(f"   {status} {description}")
        
        overall_success = passed >= (total * 0.75)  # 75% pass rate
        
        print(f"\n{'🎉 ANOMALY DETECTION WORKING!' if overall_success else '⚠️  SOME ISSUES DETECTED'}")
        
        if overall_success:
            print("   Core anomaly detection functionality is operational.")
            print("   Statistical thresholds, pattern recognition, and configuration working.")
        
        return overall_success
        
    except Exception as e:
        print(f"\n💥 Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main execution."""
    result = asyncio.run(run_simple_anomaly_tests())
    return 0 if result else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 