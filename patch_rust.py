import os

fpath = r'E:\Antigravity_multyMCP_Rust\mcp_core\src\server.rs'
with open(fpath, 'r', encoding='utf-8') as f:
    content = f.read()

# Reemplazamos la llamada hardcodeada a execute_openai_compatible
old_code = '''                    // Intentamos con la matriz de llaves (Retry/Circuit breaker loop)
                    for _ in 0..3 {
                        if !keys.is_available() {
                            break;
                        }

                        if let Some(key) = keys.get_current_key() {
                            match execute_openai_compatible(
                                provider.api_url(),
                                provider.default_model(),
                                &key,
                                &prompt
                            ).await {'''

new_code = '''                    // REGLA: No más hardcodeos. Buscar versión dinámica desde ENV/JSON.
                    let mut actual_model = provider.default_model().to_string();
                    let prefix = provider.env_prefix().split('_').next().unwrap_or("API");
                    let specific_env = format!("{}_MODEL", prefix);
                    
                    if let Ok(env_val) = std::env::var(&specific_env).or_else(|_| std::env::var("MODEL")) {
                        if !env_val.is_empty() {
                            actual_model = env_val;
                        }
                    }

                    // Intentamos con la matriz de llaves (Retry/Circuit breaker loop)
                    for _ in 0..3 {
                        if !keys.is_available() {
                            break;
                        }

                        if let Some(key) = keys.get_current_key() {
                            match execute_openai_compatible(
                                provider.api_url(),
                                &actual_model,
                                &key,
                                &prompt
                            ).await {'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)
    print("mcp_core/src/server.rs parcheado exitosamente.")
else:
    print("No se encontró el bloque a reemplazar.")
