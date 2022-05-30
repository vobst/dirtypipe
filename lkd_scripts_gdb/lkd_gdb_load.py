import os

sys.path.insert(0, os.path.dirname(__file__) + "/lkd_scripts_gdb")

try:
    gdb.parse_and_eval("0")
    gdb.execute("", to_string=True)
except:
    gdb.write("NOTE: gdb 7.2 or later required for Linux helper scripts to "
              "work.\n")
else:
    import lkd.structs
    import lkd.breakpoints
