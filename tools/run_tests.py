from pydantic import BaseModel, Field

from tools.base import BaseTool


class RunTestsArgs(BaseModel):
    targets: list[str] = Field(
        ..., description="A list of test files, directories, or specific test cases to run."
    )


class RunTestsTool(BaseTool):
    name = "run_tests"
    description = "Runs the test suite and returns structured execution results."
    args_schema = RunTestsArgs

    def run(self, targets: list[str], **kwargs) -> str:
        import os
        import subprocess
        import uuid
        import xml.etree.ElementTree as ET

        from tools.utils import format_error, truncate_output

        report_file = f".test_report.{uuid.uuid4().hex}.xml"

        import sys

        try:
            # We don't strictly care about the return code here (pytest returns 1 on failure),
            # because we will parse the XML it spits out.
            subprocess.run(
                [sys.executable, "-m", "pytest"] + targets + [f"--junitxml={report_file}"],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            return format_error(
                reason="pytest is not installed or not in PATH.",
                attempted="subprocess.run(['pytest', ...])",
                hint="Ensure you are running in the correct virtual environment where pytest is installed.",
            )
        except Exception as e:
            return format_error(
                reason=f"Failed to execute pytest: {str(e)}",
                attempted=f"run_tests(targets={targets})",
                hint="Check if the target path exists.",
            )

        if not os.path.exists(report_file):
            return format_error(
                reason="Pytest did not generate the XML report.",
                attempted=f"run_tests(targets={targets})",
                hint="Check if the target contains valid tests. It may have failed to collect tests entirely.",
            )

        try:
            tree = ET.parse(report_file)
            root = tree.getroot()

            # JUnit XML structure depends on whether it's a single <testsuite> or multiple nested.
            # Usually pytest puts everything under a top-level <testsuites> or <testsuite>.
            total_passed = 0
            total_failed = 0
            failures = []

            for testsuite in root.iter("testsuite"):
                tests = int(testsuite.get("tests", 0))
                fails = int(testsuite.get("failures", 0))
                errors = int(testsuite.get("errors", 0))
                skipped = int(testsuite.get("skipped", 0))
                total_failed += fails + errors
                total_passed += tests - fails - errors - skipped

            # Extract failure tracebacks
            for testcase in root.iter("testcase"):
                for failure in testcase.iter("failure"):
                    name = testcase.get("name", "Unknown")
                    classname = testcase.get("classname", "")
                    traceback = failure.text or ""
                    failures.append(
                        f'<test name="{classname}.{name}">\n{traceback.strip()}\n</test>'
                    )
                for error in testcase.iter("error"):
                    name = testcase.get("name", "Unknown")
                    classname = testcase.get("classname", "")
                    traceback = error.text or ""
                    failures.append(
                        f'<test name="{classname}.{name}">\n{traceback.strip()}\n</test>'
                    )

            status = "FAILED" if total_failed > 0 else "PASSED"

            xml_out = [
                "<test_run_summary>",
                f"  <status>{status}</status>",
                f"  <total_passed>{total_passed}</total_passed>",
                f"  <total_failed>{total_failed}</total_failed>",
                "</test_run_summary>",
            ]

            if failures:
                xml_out.append("<failure_details>")
                xml_out.extend(failures)
                xml_out.append("</failure_details>")

            final_output = "\n".join(xml_out)

        except Exception as e:
            final_output = format_error(
                reason=f"Failed to parse pytest XML: {str(e)}",
                attempted="XML Parsing",
                hint="The test suite output may be malformed.",
            )
        finally:
            if os.path.exists(report_file):
                os.remove(report_file)

        return truncate_output(final_output)
