"""Exact Clifford+T grid only. Arbitrary-angle synthesis is not implemented."""
import math
import numpy as np
I=np.eye(2,dtype=complex)
GATES={'H':np.array([[1,1],[1,-1]],complex)/math.sqrt(2),
       'T':np.diag([1,np.exp(1j*math.pi/4)]),
       'S':np.diag([1,1j]),'SDG':np.diag([1,-1j])}
def unitary(gates):
    u=I.copy()
    for name in gates:u=GATES[name]@u
    return u

def synthesize_grid(theta,axis='z',epsilon=1e-12):
    if axis not in ('x','y','z') or not math.isfinite(theta) or not math.isfinite(epsilon) or not 0<epsilon<1:raise ValueError('invalid synthesis argument')
    if abs(theta)>1e6:raise ValueError('angle reduction outside supported range')
    angle=math.remainder(theta,2*math.pi);k=round(angle/(math.pi/4))
    if abs(angle-k*math.pi/4)>min(epsilon,1e-12):raise NotImplementedError('off-grid rotation: use a validated approximate synthesizer')
    gates=['T']*(k%8)
    if axis=='x':gates=['H']+gates+['H']
    if axis=='y':gates=['SDG','H']+gates+['H','S']
    pauli={'x':np.array([[0,1],[1,0]]),'y':np.array([[0,-1j],[1j,0]]),'z':np.diag([1,-1])}[axis]
    target=np.cos(angle/2)*I-1j*np.sin(angle/2)*pauli
    u=unitary(gates);overlap=np.trace(target.conj().T@u);phase=overlap/abs(overlap)
    error=float(np.linalg.norm(u-phase*target,ord=2))
    if error>epsilon:raise ArithmeticError('requested tolerance below measured floating-point error')
    return gates,error
