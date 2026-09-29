"""Build the dependency-free C++17 CPU library with strict floating point."""
import argparse, os, pathlib, shutil, subprocess, sys
p=argparse.ArgumentParser();p.add_argument('--sanitize',action='store_true');p.add_argument('--debug',action='store_true');args=p.parse_args()
root=pathlib.Path(__file__).resolve().parent
build=root/'build';build.mkdir(exist_ok=True)
cxx=os.environ.get('CXX') or shutil.which('g++') or shutil.which('clang++')
if not cxx:raise SystemExit('Install a C++17 compiler (Windows: MinGW-w64 or LLVM) and add it to PATH; set CXX if needed.')
name='polydim807.dll' if sys.platform=='win32' else ('libpolydim807.dylib' if sys.platform=='darwin' else 'libpolydim807.so')
flags=['-std=c++17','-O0' if args.debug else '-O2','-g','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Wpedantic','-Wno-misleading-indentation']
if args.sanitize:flags+=['-fsanitize=undefined','-fno-sanitize-recover=all']
if sys.platform!='win32':flags+=['-fPIC']
cmd=[cxx,*flags,'-dynamiclib' if sys.platform=='darwin' else '-shared','-I'+str(root/'include'),str(root/'src/polydim.cpp'),'-o',str(build/name)]
subprocess.run(cmd,check=True)
print('Built',build/name)
