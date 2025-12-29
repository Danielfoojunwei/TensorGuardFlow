"""
Benchmark Reporting Module
Generates HTML dashboard from JSONL artifacts.
"""

import os
import json
import glob
from datetime import datetime

class ReportGenerator:
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.output_file = os.path.join(artifacts_dir, "report.html")

    def load_metrics(self):
        data = []
        # Load Microbench
        for f in glob.glob(os.path.join(self.artifacts_dir, "metrics/micro_bench_*.jsonl")):
            with open(f, 'r') as fh:
                for line in fh:
                    data.append(json.loads(line))
                    
        # Load Privacy
        privacy_data = []
        p_file = os.path.join(self.artifacts_dir, "privacy/inversion_results.json")
        if os.path.exists(p_file):
            with open(p_file, 'r') as fh:
                privacy_data = json.load(fh)

        # Load Robustness
        robust_data = {}
        r_file = os.path.join(self.artifacts_dir, "robustness/byzantine_results.json")
        if os.path.exists(r_file):
             with open(r_file, 'r') as fh:
                robust_data = json.load(fh)

        return data, privacy_data, robust_data

    def generate(self):
        micro, privacy, robust = self.load_metrics()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>TensorGuard Benchmark Report</title>
            <style>
                body {{ font-family: sans-serif; margin: 2em; }}
                h1, h2 {{ color: #2c3e50; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 2em; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .pass {{ color: green; font-weight: bold; }}
                .fail {{ color: red; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>TensorGuard Benchmark Report</h1>
            <p>Generated: {datetime.now().isoformat()}</p>

            <h2>1. Privacy Evaluation (Gradient Inversion)</h2>
            <table>
                <tr>
                    <th>Scenario</th>
                    <th>MSE (Lower is Better)</th>
                    <th>RRE (Higher is Better Privacy)</th>
                    <th>Simulated Attack PSNR</th>
                </tr>
        """
        
        for item in privacy:
            m = item['metrics']
            html += f"""
                <tr>
                    <td>{item['scenario']}</td>
                    <td>{m['mse']:.6f}</td>
                    <td>{m['rre']:.6f}</td>
                    <td>{m['simulated_attack_psnr']:.2f} dB</td>
                </tr>
            """
            
        html += """
            </table>

            <h2>2. Robustness (Byzantine Resilience)</h2>
        """
        
        if robust:
            status = "<span class='pass'>PASSED</span>" if robust.get("success") else "<span class='fail'>FAILED</span>"
            html += f"""
            <p>Status: {status}</p>
            <p>Expected Outliers: {robust.get('expected_outliers')}</p>
            <p>Detected Outliers: {robust.get('detected_outliers')}</p>
            <p>False Positives: {robust.get('false_positives')}</p>
            <p>Detection Time: {robust.get('detection_time_sec'):.4f}s</p>
            """
        else:
            html += "<p>No robustness results found.</p>"
            
        html += """
            <h2>3. Microbenchmarks</h2>
            <table>
                <tr>
                    <th>Test</th>
                    <th>Timestamp</th>
                    <th>Metrics</th>
                </tr>
        """
        
        for entry in micro:
            metrics_str = ", ".join([f"{k}={v}" for k,v in entry['metrics'].items()])
            html += f"""
                <tr>
                    <td>{entry['test_id']}</td>
                    <td>{datetime.fromtimestamp(entry['timestamp']).isoformat()}</td>
                    <td>{metrics_str}</td>
                </tr>
            """
            
        html += """
            </table>
            
            <h2>4. Compliance Evidence</h2>
            <p>See <code>evidence_pack/</code> directory for SOC2/GDPR/HIPAA artifacts.</p>
        </body>
        </html>
        """
        
        with open(self.output_file, 'w') as f:
            f.write(html)
        print(f"Report generated: {self.output_file}")

def run_report(args):
    gen = ReportGenerator()
    gen.generate()
