#include "polydim_crypto_v805.h"
#include <iostream>
#include <sddl.h>

#pragma comment(lib, "bcrypt.lib")
#pragma comment(lib, "advapi32.lib")

#ifndef NT_SUCCESS
#define NT_SUCCESS(Status) (((NTSTATUS)(Status)) >= 0)
#endif

namespace polydim {
namespace crypto {

bool polydim_hmac_sha256(const std::vector<uint8_t>& key, const std::vector<uint8_t>& data, std::vector<uint8_t>& out_mac) {
    BCRYPT_ALG_HANDLE hAlg = NULL;
    BCRYPT_HASH_HANDLE hHash = NULL;
    NTSTATUS status;

    status = BCryptOpenAlgorithmProvider(&hAlg, BCRYPT_SHA256_ALGORITHM, NULL, BCRYPT_ALG_HANDLE_HMAC_FLAG);
    if (!NT_SUCCESS(status)) return false;

    status = BCryptCreateHash(hAlg, &hHash, NULL, 0, (PUCHAR)key.data(), (ULONG)key.size(), 0);
    if (!NT_SUCCESS(status)) {
        BCryptCloseAlgorithmProvider(hAlg, 0);
        return false;
    }

    status = BCryptHashData(hHash, (PUCHAR)data.data(), (ULONG)data.size(), 0);
    if (!NT_SUCCESS(status)) {
        BCryptDestroyHash(hHash);
        BCryptCloseAlgorithmProvider(hAlg, 0);
        return false;
    }

    DWORD cbHash = 0;
    DWORD cbData = 0;
    status = BCryptGetProperty(hAlg, BCRYPT_HASH_LENGTH, (PUCHAR)&cbHash, sizeof(DWORD), &cbData, 0);
    if (!NT_SUCCESS(status)) {
        BCryptDestroyHash(hHash);
        BCryptCloseAlgorithmProvider(hAlg, 0);
        return false;
    }

    out_mac.resize(cbHash);
    status = BCryptFinishHash(hHash, (PUCHAR)out_mac.data(), cbHash, 0);
    
    BCryptDestroyHash(hHash);
    BCryptCloseAlgorithmProvider(hAlg, 0);

    return NT_SUCCESS(status);
}

bool polydim_aead_encrypt(const std::vector<uint8_t>& key, const std::vector<uint8_t>& nonce,
                          const std::vector<uint8_t>& data, const std::vector<uint8_t>& ad,
                          std::vector<uint8_t>& out_ciphertext, std::vector<uint8_t>& out_mac) {
    BCRYPT_ALG_HANDLE hAlg = NULL;
    BCRYPT_KEY_HANDLE hKey = NULL;
    NTSTATUS status;
    
    status = BCryptOpenAlgorithmProvider(&hAlg, BCRYPT_AES_ALGORITHM, NULL, 0);
    if (!NT_SUCCESS(status)) return false;

    status = BCryptSetProperty(hAlg, BCRYPT_CHAINING_MODE, (PUCHAR)BCRYPT_CHAIN_MODE_GCM, sizeof(BCRYPT_CHAIN_MODE_GCM), 0);
    if (!NT_SUCCESS(status)) { BCryptCloseAlgorithmProvider(hAlg, 0); return false; }

    status = BCryptGenerateSymmetricKey(hAlg, &hKey, NULL, 0, (PUCHAR)key.data(), (ULONG)key.size(), 0);
    if (!NT_SUCCESS(status)) { BCryptCloseAlgorithmProvider(hAlg, 0); return false; }

    BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO authInfo;
    BCRYPT_INIT_AUTH_MODE_INFO(authInfo);
    
    std::vector<uint8_t> mutable_nonce = nonce; 
    authInfo.pbNonce = mutable_nonce.data();
    authInfo.cbNonce = (ULONG)mutable_nonce.size();
    authInfo.pbAuthData = (PUCHAR)ad.data();
    authInfo.cbAuthData = (ULONG)ad.size();
    
    out_mac.resize(16); 
    authInfo.pbTag = out_mac.data();
    authInfo.cbTag = (ULONG)out_mac.size();

    out_ciphertext.resize(data.size());
    DWORD cbResult = 0;

    status = BCryptEncrypt(hKey, (PUCHAR)data.data(), (ULONG)data.size(), &authInfo, NULL, 0, 
                           (PUCHAR)out_ciphertext.data(), (ULONG)out_ciphertext.size(), &cbResult, 0);

    BCryptDestroyKey(hKey);
    BCryptCloseAlgorithmProvider(hAlg, 0);

    return NT_SUCCESS(status);
}

bool polydim_aead_decrypt(const std::vector<uint8_t>& key, const std::vector<uint8_t>& nonce,
                          const std::vector<uint8_t>& ciphertext, const std::vector<uint8_t>& mac,
                          const std::vector<uint8_t>& ad, std::vector<uint8_t>& out_plaintext) {
    BCRYPT_ALG_HANDLE hAlg = NULL;
    BCRYPT_KEY_HANDLE hKey = NULL;
    NTSTATUS status;

    status = BCryptOpenAlgorithmProvider(&hAlg, BCRYPT_AES_ALGORITHM, NULL, 0);
    if (!NT_SUCCESS(status)) return false;

    status = BCryptSetProperty(hAlg, BCRYPT_CHAINING_MODE, (PUCHAR)BCRYPT_CHAIN_MODE_GCM, sizeof(BCRYPT_CHAIN_MODE_GCM), 0);
    if (!NT_SUCCESS(status)) { BCryptCloseAlgorithmProvider(hAlg, 0); return false; }

    status = BCryptGenerateSymmetricKey(hAlg, &hKey, NULL, 0, (PUCHAR)key.data(), (ULONG)key.size(), 0);
    if (!NT_SUCCESS(status)) { BCryptCloseAlgorithmProvider(hAlg, 0); return false; }

    BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO authInfo;
    BCRYPT_INIT_AUTH_MODE_INFO(authInfo);

    std::vector<uint8_t> mutable_nonce = nonce; 
    authInfo.pbNonce = mutable_nonce.data();
    authInfo.cbNonce = (ULONG)mutable_nonce.size();
    authInfo.pbAuthData = (PUCHAR)ad.data();
    authInfo.cbAuthData = (ULONG)ad.size();
    
    std::vector<uint8_t> mutable_mac = mac;
    authInfo.pbTag = mutable_mac.data();
    authInfo.cbTag = (ULONG)mutable_mac.size();

    out_plaintext.resize(ciphertext.size());
    DWORD cbResult = 0;

    status = BCryptDecrypt(hKey, (PUCHAR)ciphertext.data(), (ULONG)ciphertext.size(), &authInfo, NULL, 0,
                           (PUCHAR)out_plaintext.data(), (ULONG)out_plaintext.size(), &cbResult, 0);

    BCryptDestroyKey(hKey);
    BCryptCloseAlgorithmProvider(hAlg, 0);

    return NT_SUCCESS(status);
}

SECURITY_ATTRIBUTES* get_secure_attributes() {
    SECURITY_ATTRIBUTES* sa = new SECURITY_ATTRIBUTES();
    sa->nLength = sizeof(SECURITY_ATTRIBUTES);
    sa->bInheritHandle = FALSE; // G-5 explicit

    // G-4 ACL/SID configuration
    // "D:(A;OICI;GA;;;BA)(A;OICI;GA;;;SY)(A;OICI;GA;;;OW)" 
    // Admins, System, Owner have full control.
    LPCSTR sddl = "D:(A;OICI;GA;;;BA)(A;OICI;GA;;;SY)(A;OICI;GA;;;OW)";
    PSECURITY_DESCRIPTOR pSD = NULL;
    
    if (ConvertStringSecurityDescriptorToSecurityDescriptorA(sddl, SDDL_REVISION_1, &pSD, NULL)) {
        sa->lpSecurityDescriptor = pSD;
    } else {
        sa->lpSecurityDescriptor = NULL;
    }

    return sa;
}

void free_secure_attributes(SECURITY_ATTRIBUTES* sa) {
    if (sa) {
        if (sa->lpSecurityDescriptor) {
            LocalFree(sa->lpSecurityDescriptor);
        }
        delete sa;
    }
}

} // namespace crypto
} // namespace polydim
