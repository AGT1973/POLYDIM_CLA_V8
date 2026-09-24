#include <iostream>
#include <vector>
#include <random>
#include <cmath>
#include <iomanip>

// Simula la cancelación catastrófica en el cálculo de Gproj^T Gproj
// mediante la fórmula Q = H - S*C - C^T*S + S^2

using namespace std;

// Producto interno punto a punto
double dot(const vector<double>& A, const vector<double>& B) {
    double sum = 0;
    for(size_t i = 0; i < A.size(); ++i) sum += A[i] * B[i];
    return sum;
}

// Escala vector
vector<double> scale(const vector<double>& A, double alpha) {
    vector<double> R(A.size());
    for(size_t i = 0; i < A.size(); ++i) R[i] = A[i] * alpha;
    return R;
}

// Suma vectores
vector<double> add(const vector<double>& A, const vector<double>& B) {
    vector<double> R(A.size());
    for(size_t i = 0; i < A.size(); ++i) R[i] = A[i] + B[i];
    return R;
}

int main() {
    size_t D = 1000000;
    cout << "Dimension D = " << D << ", K = 1 (Vector)\n";
    cout << "--------------------------------------------------\n";
    
    // Generador
    mt19937_64 rng(42);
    normal_distribution<double> dist(0.0, 1.0);
    
    // X debe ser ortonormal (norma 1)
    vector<double> X(D);
    double normX = 0;
    for(size_t i = 0; i < D; ++i) {
        X[i] = dist(rng);
        normX += X[i] * X[i];
    }
    normX = sqrt(normX);
    for(size_t i = 0; i < D; ++i) X[i] /= normX;
    
    // Z es puramente tangencial (ortogonal a X)
    vector<double> Z(D);
    for(size_t i = 0; i < D; ++i) Z[i] = dist(rng);
    
    double dotXZ = dot(X, Z);
    // Gram-Schmidt para hacer Z ortogonal a X
    for(size_t i = 0; i < D; ++i) Z[i] -= dotXZ * X[i];
    
    // Testamos diferentes magnitudes epsilon
    // G = X * S_true + epsilon * Z
    // Si epsilon es muy chico, G es casi puramente normal (paralelo a X), 
    // y la norma de la componente tangente es epsilon*||Z||.
    
    double S_true = 500.0; // Componente normal grande
    
    vector<double> epsilons = {1.0, 1e-2, 1e-4, 1e-6, 1e-8, 1e-10, 1e-12};
    
    cout << setw(10) << "Epsilon" 
         << setw(20) << "Q_direct (Gproj^2)" 
         << setw(20) << "Q_fast (Algebraic)" 
         << setw(20) << "Error Relativo" 
         << setw(15) << "rho (Peligro)" << "\n";
    cout << string(85, '-') << "\n";
    
    for(double eps : epsilons) {
        // G = S_true * X + eps * Z
        vector<double> G = add(scale(X, S_true), scale(Z, eps));
        
        // --- RUTA DIRECTA (Referencia, sin cancelación algebraica) ---
        // Gproj = G - X * (X^T G)
        double C = dot(X, G);
        double S = C; // Para K=1, C es simetrica
        vector<double> Gproj(D);
        for(size_t i = 0; i < D; ++i) {
            Gproj[i] = G[i] - X[i] * S;
        }
        double Q_direct = dot(Gproj, Gproj);
        
        // --- RUTA RÁPIDA ALGEBRAICA (V770) ---
        // Q = H - S*C - C^T*S + S^2 = H - S^2
        double H = dot(G, G);
        double Q_fast = H - S * S;
        
        // Calcular indicador rho
        double B_norm = std::abs(H) + 2.0 * std::abs(S*C) + std::abs(S*S);
        double rho = std::abs(Q_fast) / B_norm;
        
        double rel_err = std::abs(Q_fast - Q_direct) / std::max(Q_direct, 1e-30);
        
        cout << scientific << setprecision(6)
             << setw(10) << eps
             << setw(20) << Q_direct
             << setw(20) << Q_fast
             << setw(20) << rel_err
             << setw(15) << rho << "\n";
    }
    
    return 0;
}
