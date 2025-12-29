"""
tg-bench: TensorGuard Benchmark CLI
"""

import argparse
import sys
from .micro import run_micro
from .privacy.inversion import run_privacy
from .robustness.byzantine import run_robustness
from .compliance.evidence import run_evidence
from .reporting import run_report

def main():
    parser = argparse.ArgumentParser(description="TensorGuard Benchmark Suite")
    subparsers = parser.add_subparsers(dest="command", help="Benchmark Command")
    
    # 1. Micro
    micro_parser = subparsers.add_parser("micro", help="Run microbenchmarks")
    
    # 2. UpdatePkg (Pipeline) - Todo
    update_parser = subparsers.add_parser("updatepkg", help="Run client pipeline bench")
    
    # 3. Privacy
    privacy_parser = subparsers.add_parser("privacy", help="Run privacy evaluation")

    # 4. Robustness
    robustness_parser = subparsers.add_parser("robustness", help="Run robustness/byzantine tests")
    
    # 5. Evidence
    evidence_parser = subparsers.add_parser("evidence", help="Generate compliance evidence")
    
    # 6. Report
    report_parser = subparsers.add_parser("report", help="Generate HTML report")

    args = parser.parse_args()
    
    if args.command == "micro":
        run_micro(args)
    elif args.command == "updatepkg":
        print("Not implemented yet")
    elif args.command == "privacy":
        run_privacy(args)
    elif args.command == "robustness":
        run_robustness(args)
    elif args.command == "evidence":
        run_evidence(args)
    elif args.command == "report":
        run_report(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
