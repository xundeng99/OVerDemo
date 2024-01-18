import re
import time
import sys
import argparse
from sys import argv



def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", help="test contract name, can be compound, testamm", type=str)

    return parser.parse_args()

def main(args):
    start_time = time.time()
    fname = args.contract
    f = open("./" + fname + ".txt", "r")
    constraints = []
    vars_map = {}
    loop_iter = None
    reserved_token = ['(', ')', 'SUM', 'mul', 'div', 'add', 'sub', 'from', 'to', '**', "{", "}", "=", ">=" ,"!", "<=", ">", "<", "\\", "/", "*", "-", "+"]
    for l in f:
        if l.startswith("("):
            l = l.replace("add", "+")
            l = l.replace("mul", "*")
            l = l.replace("div", "/")
            l = l.replace("sub", "-")
            constraints.append(l)

    f.close()  
    var_list = []

    vars_process = ""
    vars_process_gt = ""
    vars_vec = []

    sums = {}
    c1 = []
    sum_list = []

    for idx in range(len(constraints)):
        c = constraints[idx]
        indexes_start = [x.start() for x in re.finditer('\{', c)]
        indexes_end = [x.start() for x in re.finditer('\}', c)]
        sum = []
        for i in range(len(indexes_start)):
            start = [x.start() for x in re.finditer('\{', c)]
            end = [x.start() for x in re.finditer('\}', c)]
            #print(idx, start)
            if (start  == []):
                continue
            sum_str = c[start[0] : end[0] + 1]  
            #print(sum_str)
            c= c.replace(sum_str, "sum_"+str(idx) + "_"+str(i))             
            x = sum_str.split()
            for token in x:            
                if token == "from":
                    break
                if not (token in reserved_token or token.isnumeric()) and '[' in token:
                    # if the variable is a constant
                    token_name = re.sub("\[.*\]", "", token)
                    token_name = token_name.replace(".", "_")
                    vars_vec.append(token_name)
                    sum_str = sum_str.replace(token, token_name+"[i]")
                elif not (token in reserved_token or token.isnumeric()) and '[' not in token:
                    #print(sum_str, token)
                    innermost_brackets = re.findall("\([^\(]*?"+ token + "[\s]*?\)", sum_str)
                    #print(innermost_brackets)
                    sum_str = sum_str.replace(token, "0")
                    # need to check validity of the replacement
                    # TODO: if the operator is +/- replace by 0. if operator is *// replace by 1
                    sum_str = sum_str.replace("* 0", "* 1")
                    sum_str = sum_str.replace("/ 0", "/ 1")
                    sum_str = sum_str.replace("0 - 1", "1")
            sums[("sum_"+str(idx)+"_"+str(i))] = sum_str 
            sum.append(("sum_"+str(idx)+"_"+str(i)))       
        sum_list.append(sum)    
        c1.append(c)

    for c in c1 :
        x = c.split()
        for token in x:
            if not (token in reserved_token or token.isnumeric() or 'sum' in token):
                token_name = ((token.replace("[", "_")).replace("]", "")).replace(".", "_")
                var_list.append(token_name)
                vars_map[token] = token_name
            
    #print(vars_vec)
    #print(var_list)

    programs = """
from z3 import *

def abs(x):
    return If(x >= 0,x,-x)

    """

    var_def = '''
loop_bound = 1
var_vec = []
var_vec_0 = []
var_vec_1 = []
price_vec = []
price_vec_gt = []

    '''
    vars_vec = set(vars_vec)
    var_list = set(var_list)
    price_vec = []
    price_vec_gt = []

    print("generating ", len(vars_vec), "vector variables")
    for var in vars_vec:
        print(var)

    for index, var in enumerate(vars_vec):
        var_def += """
temp_vec_0 = []
temp_vec_1 = []
for i in range(loop_bound):          
    """
        if vars_process == "":
            vars_process = var
            vars_process_gt = var
        else:
            vars_process = vars_process + ", " + var
            vars_process_gt = vars_process_gt + ", " + var

        if "price" in var or "Price" in var:
            var_gt = var + "_gt"
            vars_process_gt = vars_process_gt + ", " + var_gt
            var_def += f"""
    price_var = Real('{var}' + str(i))
    price_var_gt = Real('{var_gt}' + str(i))
    var_vec.append(price_var)
    var_vec.append(price_var_gt)
    temp_vec_0.append(price_var)
    temp_vec_1.append(price_var_gt)
    price_vec.append(price_var)
    price_vec_gt.append(price_var_gt)
    """
        else:
            var_def += f"""
    var = Real('{var}' + str(i))
    temp_vec_0.append(var)  
    temp_vec_1.append(var)
    var_vec.append(var)
        """
        var_def += f"""
var_vec_0.append(temp_vec_0)
var_vec_1.append(temp_vec_1)
    """
            
    print("generating ", len(var_list), "scalar variables")
    for var in var_list:
        print(var)
    for var in var_list:
        if vars_process == "":
            vars_process = var
        else:
            vars_process = vars_process + ", " + var

        if "price" in var or "Price" in var:
            var_gt = var + "_gt"
            vars_process_gt = vars_process_gt + ", " + var
            var_def += f"""
price_var = Real('{var}')
price_var_gt = Real('{var_gt}')
var_vec.append(price_var)
var_vec.append(price_var_gt)
var_vec_0.append(price_var) 
var_vec_1.append(price_var_gt)
price_vec.append(price_var)
price_vec_gt.append(price_var_gt)
    """
        else:
            var_def += f"""
var = Real('{var}')
var_vec_0.append(var)  
var_vec_1.append(var)  
var_vec.append(var)
    """

    #print(var_def)

    programs += var_def

    programs += """
# price, Balance and borrow amount should be greater than 0
def C00(X):
    return And([x > 0 for x in X])

def C01(P_truth, P):
    res = True
    for i in range(len(P_truth)):
        res = And(res, (abs( P_truth[i] - P[i] )/ P_truth[i] < 0.01))
    return res
    """


    sums_loop = {}
    for key in sums:
        sum = sums[key]
        #print(key)
        x = re.search(r"SUM\s(.*)from(.*)to(.*)", sum)
        expression =x.group(1)
        iter = x.group(2)
        upper_bound=x.group(3)
        assign =  re.search(r"(.*)=(.*)", iter)
        #print(assign.group(1), assign.group(2))
        loop_iter = assign.group(1)
        loop_bound = assign.group(2)
        #need to strip to remove whitespace
        expr = expression.replace("/["+ loop_iter.strip() + "/]", "[i]")
        loop = f"""
    for i in range(loop_bound):
        {key} += {expr}    
        """
        sums_loop[key] = loop
        #print(loop)


    thm = """
I1 = ForAll(var_vec, Implies(And(C00(var_vec),\\
    C01(price_vec_gt, price_vec),\\
    """

    prop = """
    And(\
    """

    for i in range(len(c1)):
        c = c1[i]
        loops = sum_list[i]
        sums= ""
        for key in loops:
            #print(sums_loop[key])
            sums += f"{key} = 0"
            sums = sums + sums_loop[key]
        prog =f"""
def C{i} ({vars_process}):
    {sums}
    return {c}    
    """
        '''
        prog = prog.replace("add", "+")
        prog = prog.replace("mul", "*")
        prog = prog.replace("div", "/")
        prog = prog.replace("sub", "-")
        '''

        for key in vars_map:
            prog = prog.replace(key, vars_map[key])
        programs = programs + prog

        if (i == (len(c1)) - 1):
            thm = thm + f"""
    C{i}(*var_vec_0)),\\
    """
            prop = prop + f"""
    C{i}(*var_vec_1))))\n   
    """
        else:
            thm = thm + f"""
    C{i}(*var_vec_0),\\
    """
            prop = prop + f"""        
    C{i}(*var_vec_1), \\
    """

    f = open("./generated_"+ fname + ".py", "w")
    f.write(programs + thm + prop)
    provesmt = """
prove(I1)
    """
    f.write(provesmt)
    f.close()
    print("Done generating python file --- %s seconds ---" % (time.time() - start_time))

    
if __name__ == '__main__':
    assert len(argv) > 1
    args = parse_args()    
    main(args)