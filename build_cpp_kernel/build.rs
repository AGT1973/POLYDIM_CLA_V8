fn main() {
    cc::Build::new()
        .cpp(true)
        .file("../POLYDIM_V751/src/polydim_kernel.cpp")
        .include("../POLYDIM_V751/include")
        .define("POLYDIM_BUILD_DLL", None)
        .flag_if_supported("/O2")
        .flag_if_supported("/openmp")
        .flag_if_supported("-O3")
        .flag_if_supported("-fopenmp")
        .compile("polydim_cpp_kernel");

    println!("cargo:rustc-link-lib=polydim_cpp_kernel");
}
