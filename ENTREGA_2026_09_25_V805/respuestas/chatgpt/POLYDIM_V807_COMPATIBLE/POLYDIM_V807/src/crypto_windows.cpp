#include "polydim_crypto_windows.h"
#ifdef _WIN32
#include <sddl.h>
#include <limits>
#include <new>
#pragma comment(lib,"bcrypt.lib")
#pragma comment(lib,"advapi32.lib")
namespace polydim {namespace crypto {
namespace {
bool ok(NTSTATUS s){return s>=0;}
bool length(size_t n){return n<=std::numeric_limits<ULONG>::max();}
void erase(std::vector<uint8_t>& a){if(!a.empty())SecureZeroMemory(a.data(),a.size());a.clear();}
struct Alg{BCRYPT_ALG_HANDLE h=nullptr;~Alg(){if(h)BCryptCloseAlgorithmProvider(h,0);}};
struct Key{BCRYPT_KEY_HANDLE h=nullptr;~Key(){if(h)BCryptDestroyKey(h);}};
struct Hash{BCRYPT_HASH_HANDLE h=nullptr;~Hash(){if(h)BCryptDestroyHash(h);}};
struct Secret{std::vector<uint8_t> b;~Secret(){erase(b);}};
bool crypt(bool encrypt,const std::vector<uint8_t>& key,const std::vector<uint8_t>& nonce,const std::vector<uint8_t>& data,const std::vector<uint8_t>& ad,std::vector<uint8_t>& result,std::vector<uint8_t>& tag){
 if((key.size()!=16&&key.size()!=24&&key.size()!=32)||nonce.size()!=12||!length(data.size())||!length(ad.size())||tag.size()!=16)return false;
 Alg alg;if(!ok(BCryptOpenAlgorithmProvider(&alg.h,BCRYPT_AES_ALGORITHM,nullptr,0)))return false;
 if(!ok(BCryptSetProperty(alg.h,BCRYPT_CHAINING_MODE,(PUCHAR)BCRYPT_CHAIN_MODE_GCM,sizeof(BCRYPT_CHAIN_MODE_GCM),0)))return false;
 Key k;if(!ok(BCryptGenerateSymmetricKey(alg.h,&k.h,nullptr,0,(PUCHAR)key.data(),(ULONG)key.size(),0)))return false;
 BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO auth;BCRYPT_INIT_AUTH_MODE_INFO(auth);
 auth.pbNonce=(PUCHAR)nonce.data();auth.cbNonce=(ULONG)nonce.size();auth.pbAuthData=(PUCHAR)ad.data();auth.cbAuthData=(ULONG)ad.size();auth.pbTag=tag.data();auth.cbTag=16;
 // A non-null output buffer also supports authenticated empty plaintext.
 Secret temporary;temporary.b.resize(data.empty()?1:data.size());ULONG written=0;
 NTSTATUS st=encrypt?BCryptEncrypt(k.h,(PUCHAR)data.data(),(ULONG)data.size(),&auth,nullptr,0,temporary.b.data(),(ULONG)temporary.b.size(),&written,0):BCryptDecrypt(k.h,(PUCHAR)data.data(),(ULONG)data.size(),&auth,nullptr,0,temporary.b.data(),(ULONG)temporary.b.size(),&written,0);
 if(!ok(st)||written!=data.size())return false;
 temporary.b.resize(written);result.swap(temporary.b);return true;
}
}
bool hmac_sha256(const std::vector<uint8_t>& key,const std::vector<uint8_t>& data,std::vector<uint8_t>& mac)noexcept{
 // Output aliasing with inputs is unsupported and rejected before clearing.
 if(&mac==&key||&mac==&data)return false;erase(mac);
 try{if(!length(key.size())||!length(data.size()))return false;Alg a;Hash h;
 if(!ok(BCryptOpenAlgorithmProvider(&a.h,BCRYPT_SHA256_ALGORITHM,nullptr,BCRYPT_ALG_HANDLE_HMAC_FLAG)))return false;
 if(!ok(BCryptCreateHash(a.h,&h.h,nullptr,0,(PUCHAR)key.data(),(ULONG)key.size(),0)))return false;
 if(!ok(BCryptHashData(h.h,(PUCHAR)data.data(),(ULONG)data.size(),0)))return false;
 std::vector<uint8_t> tmp(32);if(!ok(BCryptFinishHash(h.h,tmp.data(),32,0)))return false;mac.swap(tmp);return true;
 }catch(...){erase(mac);return false;}
}
bool aead_encrypt(const std::vector<uint8_t>& key,const std::vector<uint8_t>& nonce,const std::vector<uint8_t>& data,const std::vector<uint8_t>& ad,std::vector<uint8_t>& cipher,std::vector<uint8_t>& tag)noexcept{
 if(&cipher==&tag||&cipher==&key||&cipher==&nonce||&cipher==&data||&cipher==&ad||&tag==&key||&tag==&nonce||&tag==&data||&tag==&ad)return false;
 erase(cipher);erase(tag);try{std::vector<uint8_t> t(16);if(!crypt(true,key,nonce,data,ad,cipher,t))return false;tag.swap(t);return true;}catch(...){erase(cipher);erase(tag);return false;}
}
bool aead_decrypt(const std::vector<uint8_t>& key,const std::vector<uint8_t>& nonce,const std::vector<uint8_t>& cipher,const std::vector<uint8_t>& tag,const std::vector<uint8_t>& ad,std::vector<uint8_t>& plain)noexcept{
 if(&plain==&key||&plain==&nonce||&plain==&cipher||&plain==&tag||&plain==&ad)return false;erase(plain);
 try{if(tag.size()!=16)return false;auto t=tag;return crypt(false,key,nonce,cipher,ad,plain,t);}catch(...){erase(plain);return false;}
}
SECURITY_ATTRIBUTES* secure_attributes()noexcept{
 auto sa=new(std::nothrow) SECURITY_ATTRIBUTES{};if(!sa)return nullptr;
 sa->nLength=sizeof(*sa);sa->bInheritHandle=FALSE;
 if(!ConvertStringSecurityDescriptorToSecurityDescriptorA("D:(A;OICI;GA;;;BA)(A;OICI;GA;;;SY)(A;OICI;GA;;;OW)",SDDL_REVISION_1,&sa->lpSecurityDescriptor,nullptr)){delete sa;return nullptr;}
 return sa;
}
void free_secure_attributes(SECURITY_ATTRIBUTES* sa)noexcept{if(sa){if(sa->lpSecurityDescriptor)LocalFree(sa->lpSecurityDescriptor);delete sa;}}
}}
#endif
