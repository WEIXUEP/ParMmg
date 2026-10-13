"""Exercise split and bundled METIS installations without production libraries."""

from pathlib import Path
import subprocess
import tempfile
import unittest


MODULES = Path(__file__).resolve().parents[1] / "modules"


class FindMetisTest(unittest.TestCase):
    def run_command(self, *args, succeeds=True):
        result = subprocess.run(args, text=True, capture_output=True, timeout=60)
        if succeeds:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def test_dependency_detection(self):
        with tempfile.TemporaryDirectory(prefix="parmmg-metis-test-") as directory:
            root = Path(directory)
            source = root / "fixture"
            source.mkdir()
            (source / "metis.h").write_text("typedef int idx_t;\n")
            (source / "helper.c").write_text("int gk_helper(void) { return 0; }\n")
            (source / "split.c").write_text(
                "extern int gk_helper(void);\n"
                "int METIS_NodeND(void) { return gk_helper(); }\n")
            (source / "bundled.c").write_text(
                "int METIS_NodeND(void) { return 0; }\n")
            (source / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.10)\n"
                "project(MetisFixture C)\n"
                "add_library(helper STATIC helper.c)\n"
                "set_target_properties(helper PROPERTIES OUTPUT_NAME GKlib)\n"
                "add_library(split STATIC split.c)\n"
                "set_target_properties(split PROPERTIES OUTPUT_NAME metis)\n"
                "add_library(bundled STATIC bundled.c)\n"
                "set_target_properties(bundled PROPERTIES OUTPUT_NAME metis "
                "ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bundled)\n"
                "install(TARGETS split ARCHIVE DESTINATION split/lib)\n"
                "install(TARGETS bundled ARCHIVE DESTINATION bundled/lib)\n"
                "install(TARGETS helper ARCHIVE DESTINATION gklib/lib)\n"
                "install(FILES metis.h DESTINATION split/include)\n"
                "install(FILES metis.h DESTINATION bundled/include)\n")
            prefix = root / "install"
            self.run_command("cmake", "-S", str(source), "-B", str(root / "build"),
                             f"-DCMAKE_INSTALL_PREFIX={prefix}")
            self.run_command("cmake", "--build", str(root / "build"))
            self.run_command("cmake", "--install", str(root / "build"))
            probe = root / "probe"
            probe.mkdir()
            (probe / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.10)\n"
                "project(MetisProbe C)\n"
                f'list(PREPEND CMAKE_MODULE_PATH "{MODULES.as_posix()}")\n'
                "find_package(METIS REQUIRED)\n"
                "if(NOT METIS_INTSIZE EQUAL 4)\n"
                '  message(FATAL_ERROR "Incorrect idx_t size")\n'
                "endif()\n")
            for mode, flags in (
                    ("split", [f"-DGKLIB_DIR={prefix / 'gklib'}",
                               "-DMETIS_GKLIB_LIBRARY:FILEPATH="]),
                    ("explicit", [f"-DMETIS_GKLIB_LIBRARY={prefix / 'gklib/lib/libGKlib.a'}"]),
                    ("bundled", ["-DMETIS_GKLIB_LIBRARY:FILEPATH="])):
                metis = prefix / ("bundled" if mode == "bundled" else "split")
                self.run_command("cmake", "-S", str(probe), "-B", str(root / mode),
                                 f"-DMETIS_DIR={metis}", *flags)
            log = self.run_command(
                "cmake", "-S", str(probe), "-B", str(root / "missing"),
                f"-DMETIS_DIR={prefix / 'split'}",
                f"-DMETIS_GKLIB_LIBRARY={root / 'absent.a'}", succeeds=False)
            self.assertIn("Could NOT find METIS", log)


if __name__ == "__main__":
    unittest.main()
