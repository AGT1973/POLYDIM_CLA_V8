@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
cl /O2 /fp:precise /openmp /std:c++17 /IE:\POLYDIM_EINSOF\POLYDIM_V751\include /LD E:\POLYDIM_EINSOF\ENTREGA_2026_09_18_V753\kernel_cpp_v753.cpp /Fe:E:\POLYDIM_EINSOF\ENTREGA_2026_09_18_V753\bin\polydim_kernel.dll
