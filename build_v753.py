import subprocess, os

vswhere = r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"
p = subprocess.run([vswhere, "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"], capture_output=True, text=True)
install_path = p.stdout.strip()
vcvars = os.path.join(install_path, "VC", "Auxiliary", "Build", "vcvars64.bat")

bat_content = f"""@echo off
call "{vcvars}"
cl /O2 /fp:precise /openmp /std:c++17 /IE:\\POLYDIM_EINSOF\\POLYDIM_V751\\include /LD E:\\POLYDIM_EINSOF\\ENTREGA_2026_09_18_V753\\kernel_cpp_v753.cpp /Fe:E:\\POLYDIM_EINSOF\\ENTREGA_2026_09_18_V753\\bin\\polydim_kernel.dll
"""

with open(r"E:\POLYDIM_EINSOF\build_v753.bat", "w") as f:
    f.write(bat_content)

p_build = subprocess.run([r"E:\POLYDIM_EINSOF\build_v753.bat"], capture_output=True, text=True)
print("BUILD OUTPUT:\n", p_build.stdout)
if p_build.stderr:
    print("BUILD STDERR:\n", p_build.stderr)
print("EXIT CODE:", p_build.returncode)
