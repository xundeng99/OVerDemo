
from z3 import *

def abs(x):
    return If(x >= 0,x,-x)

    
loop_bound = 1
var_vec = []
var_vec_0 = []
var_vec_1 = []
price_vec = []
price_vec_gt = []

    
temp_vec_0 = []
temp_vec_1 = []
for i in range(loop_bound):          
    
    var = Real('vars_borrowBalance' + str(i))
    temp_vec_0.append(var)  
    temp_vec_1.append(var)
    var_vec.append(var)
        
var_vec_0.append(temp_vec_0)
var_vec_1.append(temp_vec_1)
    
temp_vec_0 = []
temp_vec_1 = []
for i in range(loop_bound):          
    
    var = Real('vars_exchangeRateMantissa' + str(i))
    temp_vec_0.append(var)  
    temp_vec_1.append(var)
    var_vec.append(var)
        
var_vec_0.append(temp_vec_0)
var_vec_1.append(temp_vec_1)
    
temp_vec_0 = []
temp_vec_1 = []
for i in range(loop_bound):          
    
    var = Real('vars_cTokenBalance' + str(i))
    temp_vec_0.append(var)  
    temp_vec_1.append(var)
    var_vec.append(var)
        
var_vec_0.append(temp_vec_0)
var_vec_1.append(temp_vec_1)
    
temp_vec_0 = []
temp_vec_1 = []
for i in range(loop_bound):          
    
    var = Real('markets_collateralFactorMantissa' + str(i))
    temp_vec_0.append(var)  
    temp_vec_1.append(var)
    var_vec.append(var)
        
var_vec_0.append(temp_vec_0)
var_vec_1.append(temp_vec_1)
    
temp_vec_0 = []
temp_vec_1 = []
for i in range(loop_bound):          
    
    price_var = Real('vars_oraclePriceMantissa' + str(i))
    price_var_gt = Real('vars_oraclePriceMantissa_gt' + str(i))
    var_vec.append(price_var)
    var_vec.append(price_var_gt)
    temp_vec_0.append(price_var)
    temp_vec_1.append(price_var_gt)
    price_vec.append(price_var)
    price_vec_gt.append(price_var_gt)
    
var_vec_0.append(temp_vec_0)
var_vec_1.append(temp_vec_1)
    
var = Real('redeemTokens')
var_vec_0.append(var)  
var_vec_1.append(var)  
var_vec.append(var)
    
price_var = Real('vars_oraclePriceMantissa_i')
price_var_gt = Real('vars_oraclePriceMantissa_i_gt')
var_vec.append(price_var)
var_vec.append(price_var_gt)
var_vec_0.append(price_var) 
var_vec_1.append(price_var_gt)
price_vec.append(price_var)
price_vec_gt.append(price_var_gt)
    
var = Real('markets_assets_i_collateralFactorMantissa')
var_vec_0.append(var)  
var_vec_1.append(var)  
var_vec.append(var)
    
var = Real('borrowAmount')
var_vec_0.append(var)  
var_vec_1.append(var)  
var_vec.append(var)
    
var = Real('vars_exchangeRateMantissa_i')
var_vec_0.append(var)  
var_vec_1.append(var)  
var_vec.append(var)
    
# price, Balance and borrow amount should be greater than 0
def C00(X):
    return And([x > 0 for x in X])

def C01(P_truth, P):
    res = True
    for i in range(len(P_truth)):
        res = And(res, (abs( P_truth[i] - P[i] )/ P_truth[i] < 0.01))
    return res
    
def C0 (vars_borrowBalance, vars_exchangeRateMantissa, vars_cTokenBalance, markets_collateralFactorMantissa, vars_oraclePriceMantissa, redeemTokens, vars_oraclePriceMantissa_i, markets_assets_i_collateralFactorMantissa, borrowAmount, vars_exchangeRateMantissa_i):
    sum_0_0 = 0
    for i in range(loop_bound):
        sum_0_0 += ( ( markets_collateralFactorMantissa[i] * ( vars_exchangeRateMantissa[i] * vars_oraclePriceMantissa[i] )  )  * vars_cTokenBalance[i] )      
        sum_0_1 = 0
    for i in range(loop_bound):
        sum_0_1 += ( vars_oraclePriceMantissa[i] * vars_borrowBalance[i] )      
        
    return ( ( sum_0_0  - ( ( sum_0_1  + ( ( markets_assets_i_collateralFactorMantissa * ( vars_exchangeRateMantissa_i * vars_oraclePriceMantissa_i )  )  * redeemTokens )  )  + ( vars_oraclePriceMantissa_i * borrowAmount )  )  )  > 0 ) 
    
    
I1 = ForAll(var_vec, Implies(And(C00(var_vec),\
    C01(price_vec_gt, price_vec),\
    
    C0(*var_vec_0)),\
    
    And(    
    C0(*var_vec_1))))
   
    
prove(I1)
    