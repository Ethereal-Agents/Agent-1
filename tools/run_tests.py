import subprocess
import uuid
import xml.etree.ElementTree as ET

from pydantic import BaseModel, Field

from tools.base import BaseTool
from tools.utils import format_error, truncate_output


class RunTestsArgs(BaseModel):
    targets: list[str] = Field(
        ..., description="A list of test files, directories, or specific test cases to run."
    )


class RunTestsTool(BaseTool):
    name = "run_tests"
    description = "Runs the test suite using pytest and returns structured execution results. Note: This tool specifically expects and runs pytest."
    args_schema = RunTestsArgs

    def run(self, targets: list[str], **kwargs) -> str:
        report_file = f"/tmp/.test_report.{uuid.uuid4().hex}.xml"

        try:
            # We don't strictly care about the return code here (pytest returns 1 on failure),
            # because we will parse the XML it spits out.
            cmd_str = f"python -m pytest {' '.join(targets)} --junitxml={report_file}"
            result = self.env.run_bash(cmd_str, timeout=300)
        except subprocess.TimeoutExpired:
            return format_error(
                reason="Pytest execution timed out after 300 seconds.",
                attempted=cmd_str,
                hint="One of the tests might contain an infinite loop or require user input.",
            )
        except Exception as e:
            return format_error(
                reason=f"Failed to execute pytest: {str(e)}",
                attempted=f"run_tests(targets={targets})",
            )

        if result.returncode == 127:
            return format_error(
                reason="pytest or python is not installed or not in PATH.",
                attempted=cmd_str,
                hint="Ensure you are running in an environment where pytest is installed.",
            )

        try:
            xml_content = self.env.read_file(report_file)
        except FileNotFoundError:
            return f"[TEST EXECUTION FAILED]\nPytest did not generate the XML report. The testing framework likely crashed.\n\n<stdout>\n{truncate_output(result.stdout)}\n</stdout>\n<stderr>\n{truncate_output(result.stderr)}\n</stderr>"
        except Exception as e:
            return format_error(
                reason=f"Failed to read the generated pytest XML report: {str(e)}",
                attempted=f"read_file('{report_file}')",
            )

        try:
            root = ET.fromstring(xml_content)

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
            try:
                self.env.run_bash(f"rm -f {report_file}", timeout=10)
            except Exception:
                pass

        return truncate_output(final_output)
