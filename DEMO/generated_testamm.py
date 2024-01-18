
from z3 import *

def abs(x):
    return If(x >= 0,x,-x)

    
loop_bound = 1
var_vec = []
var_vec_0 = []
var_vec_1 = []
price_vec = []
price_vec_gt = []

    
var = Real('USDCdeposits_msg_sender')
var_vec_0.append(var)  
var_vec_1.append(var)  
var_vec.append(var)
    
var = Real('collateralizationRatio')
var_vec_0.append(var)  
var_vec_1.append(var)  
var_vec.append(var)
    
var = Real('amount')
var_vec_0.append(var)  
var_vec_1.append(var)  
var_vec.append(var)
    
price_var = Real('getPriceUSDCETH')
price_var_gt = Real('getPriceUSDCETH_gt')
var_vec.append(price_var)
var_vec.append(price_var_gt)
var_vec_0.append(price_var) 
var_vec_1.append(price_var_gt)
price_vec.append(price_var)
price_vec_gt.append(price_var_gt)
    
# price, Balance and borrow amount should be greater than 0
def C00(X):
    return And([x > 0 for x in X])

def C01(P_truth, P):
    res = True
    for i in range(len(P_truth)):
        res = And(res, (abs( P_truth[i] - P[i] )/ P_truth[i] < 0.01))
    return res
    
def C0 (USDCdeposits_msg_sender, collateralizationRatio, amount, getPriceUSDCETH):
    
    return ( amount <= ( ( ( ( USDCdeposits_msg_sender * getPriceUSDCETH )  / 1000000000000000000 )  * collateralizationRatio )  / 10000 )  ) 
    
    
I1 = ForAll(var_vec, Implies(And(C00(var_vec),\
    C01(price_vec_gt, price_vec),\
    
    C0(*var_vec_0)),\
    
    And(    
    C0(*var_vec_1))))
   
    
prove(I1)
    