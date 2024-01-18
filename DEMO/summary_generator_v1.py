import sys
import argparse
from sys import argv

import time
import re
from slither.slither import Slither

from slither.core.cfg.node import NodeType 
from slither.core.expressions import (Identifier, IndexAccess, MemberAccess, UnaryOperation, Literal)
from slither.slithir.variables import (Constant, LocalIRVariable, ReferenceVariable, StateIRVariable, TemporaryVariable, TupleVariable,)

from slither.slithir.operations.assignment import Assignment
from slither.slithir.operations.binary import Binary
from slither.slithir.operations.binary import BinaryType
from slither.slithir.operations.unary import Unary
from slither.slithir.operations.index import Index
from slither.slithir.operations.member import Member
from slither.slithir.operations.condition import Condition
from slither.slithir.operations.solidity_call import SolidityCall
from slither.slithir.operations.internal_call import InternalCall
from slither.slithir.operations.library_call import LibraryCall
from slither.slithir.operations.high_level_call import HighLevelCall
from slither.slithir.operations.low_level_call import LowLevelCall
from slither.slithir.operations.type_conversion import TypeConversion
from slither.slithir.operations.length import Length
#from slither.slithir.operations.delete import Delete
from slither.slithir.operations.unpack import Unpack
from slither.slithir.operations.return_operation import Return



class IndexRead:   
    def __init__(self, array, index):
        self.array = array
        self.index = index

    def __str__(self) -> str:
        return str(self.array) + "["+ str(self.index) + "]"

class MathNode:

    def __init__(self, lhs, rhs, op):
        self.rhs = rhs
        self.lhs = lhs
        self.op = op    

    def __str__(self) -> str:
        return "( " + str(self.lhs) + " " + str(self.op) + " " + str(self.rhs) + " ) "

class ConditionNode:
    def __init__(self, lhs, rhs, op):
        self.rhs = rhs
        self.lhs = lhs
        self.op = op    

    def __str__(self) -> str:
        return str(self.lhs) + " " + str(self.op) + " " + str(self.rhs)

class AccNode:
    def __init__(self, lhs, expression, start, end, iter):
        self.lhs = lhs
        self.expression = expression
        self.start = start
        self.end = end
        self.iter = iter
    
    def __str__(self) -> str:
        return "{ SUM " + str(self.expression) + " from " + str(self.iter) + "  = " + str(self.start) + " to " + str(self.end) + " } "

class Constraint:
    def __init__(self, expression):
        self.expression = expression

    def __str__(self) -> str:
        return str(self.expression)

class Loop:
    def __init__(self, func, iter, lower_bound, upper_bound) -> None:
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.iter = iter
        self.summary = []
        self.dep = [iter,]
    
    def set_lower_bound(self, lower_bound):
        self.lower_bound = lower_bound
    
    def set_upper_bound(self, upper_bound):
        self.upper_bound = upper_bound

class Func:
    def __init__(self, name, contract, func_nodes, input_args, state_variables, func, slither):
        self.name = name
        self.contract = contract
        self.nodes = func_nodes
        self.input_args = input_args
        self.state_vars = state_variables
        self.constraints = []
        # symbols to value
        self.Value_map = {}
        # reference to symbols
        self.Refs_map = {}
        # dependency on oracle price input
        self.Price_dep = []
        # return from functions str -> functionn_name
        self.return_from_func = {}
        # assume there's only one loop in the function
        self.loop = None
        # slither funciton obj
        self.func_obj = func

        self.returns = []

        self.slither = slither

        self.flagif = False
        self.flagcount = 0


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", help="test contract name, can be aave-borrow, aave-liq, compound, testamm, morpho, warp, dforce, euler", type=str)

    return parser.parse_args()

def parse_single_ir_assign(ir, func):
    # REF# := Value
    # All safe math expression ends with assign the tmp value to the REF
    if isinstance(ir, Assignment):
        rhs = str(ir._rvalue)
        lhs = str(ir._lvalue) 
        #print(("In assign",str(ir._lvalue), str(ir._rvalue)) 

        # if not Constant, read from value map 
        if isinstance(ir._rvalue, Constant):
            if lhs in func.Refs_map:
                func.Value_map[func.Refs_map[lhs]] = rhs
                func.Value_map[lhs] = rhs
                return 
            else:
                func.Value_map[lhs] = rhs
                return

        # special case
        # a = a.add(exp1) -> a = sum (exp1) when exp1 depends on iter i
        # if followed by a = a.add(exp2) -> a = sum(exp1) + exp1 when exp2 doesn't depends on iter i (case1)
        # if followed by a = a.add(exp3) -> a = sum(exp1 + exp3) when exp3 depends on iter i (case2)
        elif isinstance(func.Value_map[rhs], MathNode) and (str(func.Value_map[rhs].op) in ["add", "+",] ) and func.loop is not None:
            #print(("heree")
            expr = func.Value_map[rhs]
            if lhs in func.Refs_map or lhs in func.Value_map:
                tmp_lhs = func.Refs_map[lhs] if lhs in func.Refs_map else lhs
                # no need to adjust dependencies
                #print("in assign ", tmp_lhs, " | " , expr.rhs, expr.lhs, expr.rhs in func.loop.dep)
                if str(tmp_lhs) == str(expr.lhs) and expr.rhs in func.loop.dep:
                    if not isinstance(func.Value_map[expr.lhs], AccNode):
                        func.Value_map[tmp_lhs] = AccNode(str(lhs), expr.rhs, func.loop.lower_bound, func.loop.upper_bound, func.loop.iter)
                        func.Value_map[lhs] = func.Value_map[tmp_lhs]
                        #print((lhs, func.Value_map[lhs])
                        if expr.rhs in func.Price_dep:
                            func.Price_dep.append(tmp_lhs)
                        return
                    else:                        
                        raise Exception("case not Handled. Loop not resolved.")
                elif str(tmp_lhs) == str(expr.rhs) and expr.lhs in func.loop.dep:
                    if not isinstance(func.Value_map[expr.hrs], AccNode):
                        func.Value_map[func.Refs_map[lhs]] = AccNode(str(rhs), expr.lhs, func.loop.lower_bound, func.loop.upper_bound, func.loop.iter)
                        func.Value_map[lhs] = func.Value_map[func.Refs_map[lhs]]
                        if expr.lhs in func.Price_dep:
                            func.Price_dep.append(func.Refs_map[lhs])
                        return  
                    else:
                        raise Exception("case not Handled. Loop not resolved.")
                    # TODO to cover the special case 2  
                    #raise Exception("sum not resolved")     

        if lhs in func.Refs_map: 
            # if it's a return value from other function, remain as symbol 
            if not rhs in func.return_from_func: 
                func.Value_map[func.Refs_map[lhs]] = func.Value_map[rhs]
                func.Value_map[lhs] = func.Value_map[rhs]
            else:
                if func.loop is not None:
                    func.Value_map[func.Refs_map[lhs]] = str(func.Refs_map[lhs]) + "[" + str(func.loop.iter) + "]"
                    func.Value_map[lhs] = str(func.Refs_map[lhs]) + "[" + str(func.loop.iter) + "]"
                else:
                    func.Value_map[func.Refs_map[lhs]] = str(func.Refs_map[lhs])
                    func.Value_map[lhs] = str(func.Refs_map[lhs])
    
             # update dependencies
            if rhs in func.Price_dep:
                func.Price_dep.append(func.Refs_map[lhs])
                #print(("updating price dependency", func.Refs_map[lhs])
            # in case of mathnode
            elif ir._rvalue in func.Price_dep:
                func.Price_dep.append(func.Refs_map[lhs])
                #print(("updating price dependency", func.Refs_map[lhs])

            if func.loop is not None and rhs in func.loop.dep:
                func.loop.dep.append(lhs)
                func.loop.dep.append(func.Refs_map[lhs])
                func.loop.dep.append(func.Value_map[func.Refs_map[lhs]])
                #print(("updating loop dep", func.Refs_map[lhs], lhs,func.Value_map[func.Refs_map[lhs]])
                
        else:
            if rhs in func.Price_dep:
                func.Price_dep.append(lhs)
                #print(("updating price dep", rhs)
            
            if func.loop is not None and rhs in func.loop.dep:
                func.loop.dep.append(lhs)
                #print(("updating loop dep", lhs)

            # if it's a return value from other function, remain as symbol
            if not rhs in func.return_from_func: 
                func.Value_map[lhs] = func.Value_map[rhs]
                #print(("here",func.Value_map[lhs])
            else:
                if func.loop is not None:
                    #print(("here",lhs, func.loop.iter)
                    func.Value_map[lhs] = str(lhs) + "[" + str(func.loop.iter) + "]"
                    #print((func.Value_map[lhs])
                    func.loop.dep.append(func.Value_map[lhs])
                else:
                    func.Value_map[lhs] = func.Value_map[rhs]
                return         
           
    else:
        raise Exception("Not assignment instance")

def parse_single_ir_memebr(ir, func):
    # REF# -> loval_var.member1
    if isinstance(ir, Member):
        # memebr name is struct_member
        struct_name = str(ir._variable_left)
        #print(("struct name", struct_name)
        if str(ir._variable_left) in func.Refs_map:
            struct_name = func.Refs_map[struct_name]
        
        if struct_name not in func.Value_map:
            func.Value_map[struct_name] = struct_name
        
        struct_name = str(func.Value_map[struct_name])

        member_name = struct_name + "." + str(ir._variable_right)
        #print(("reference {} points to {}".format(str(ir._lvalue), member_name))
       
        # if see the variable for the first time, add to the vars_map
        if member_name not in func.Value_map:
            func.Value_map[member_name] = member_name

        # check if struct is in dependency_list  
        if func.loop is not None:   
            if str(ir._variable_left) in func.loop.dep:
                func.loop.dep.append(member_name)
                func.loop.dep.append(str(ir._lvalue))
                #print(("updating loop dependencies",str(ir._lvalue))
            elif str(member_name) in func.loop.dep:
                func.loop.dep.append(str(ir._lvalue))
                #print(("updating loop dependencies",str(ir._lvalue))

        # check if struct is in price dependency_list     
        if str(ir._variable_left) in func.Price_dep:
            func.Price_dep.append(member_name)
            func.Price_dep.append(str(ir._lvalue))
        
        elif str(member_name) in func.Price_dep:
            func.Price_dep.append(str(ir._lvalue))

        # add the newly created REF_# to the Refs_map              
        func.Refs_map[str(ir._lvalue)] = member_name
        # if the member evaluates to a value assign this value to REF
        func.Value_map[str(ir._lvalue)] = func.Value_map[member_name]
    else:
        raise Exception("Not a member instance")

def parse_single_ir_index(ir, func):
    # Ref -> Data[i]
    array_name = str(ir._variables[0])
    if array_name in func.Refs_map:
        array_name = func.Refs_map[array_name]
    index = str(ir._variables[1]) 
    lhs = str(ir._lvalue)
    #print(("indexing", lhs, array_name, ir._variables[1])

    if index in func.Refs_map:
        index = func.Refs_map[index]
    
    if index not in func.Value_map:
        func.Value_map[index] = index
    func.Value_map[lhs] = IndexRead(array_name, func.Value_map[index])

    # Add dependencies    
    if index in func.Price_dep:
        func.Price_dep.append(lhs)
        ##print(("updating depencies in side ir_index", lhs, func.loop.dep[str(index)])

    if func.loop is not None and (index in func.loop.dep or array_name in func.loop.dep or str(ir._variables[0]) in func.loop.dep) :
        func.loop.dep.append(lhs)
        #print(("updating depencies in side ir_index", lhs)
    return

def parse_single_ir_safe_math(ir, func):
    arg0 = str(ir._arguments[0])
    arg1 = str(ir._arguments[1])
    tmp_node = None
    # Both the operands should be in VALUE_MAP
    # TODO handle constant 
    if arg0 in func.Value_map and arg1 in func.Value_map:
        #print(("inside safe math", arg0, arg1, ir._function_name)
        v1 = func.Value_map[arg0]
        v2 = func.Value_map[arg1]
        tmp = str(ir._lvalue)
        
        tmp_node = MathNode(v1, v2, ir._function_name)
        if str(ir._lvalue) in func.Refs_map:
            func.Value_map[func.Refs_map[str(ir._lvalue)]] = tmp_node

        # return a tmp variable 
        func.Value_map[str(ir._lvalue)] = tmp_node

        # if both operands depend on the same variable
        # update the dependency list  
        if func.loop is not None:
            #print((arg0 in func.loop.dep, arg1 in func.loop.dep)
            if arg0 in func.loop.dep and arg1 in func.loop.dep:
                #print(("inside safe math", arg0, arg1, "updating", str(ir._lvalue))
                func.loop.dep.append(str(ir._lvalue))
                func.loop.dep.append(tmp_node)
            
        if arg0 in func.Price_dep or arg1 in func.Price_dep:
            func.Price_dep.append(str(ir._lvalue))
            func.Price_dep.append(tmp_node)
            #print(("updating price dependency in safe math", str(ir._lvalue))

    elif arg0 in func.Value_map and isinstance(ir._arguments[1], Constant):
        tmp_node = MathNode(func.Value_map[arg0], arg1, ir._function_name)
        # record the tmp value
        func.Value_map[str(ir._lvalue)] = tmp_node
        # update dependencies
        if (arg0 in func.Price_dep):
            func.Price_dep.append(str(ir._lvalue))
            func.Price_dep.append(tmp_node)

        if func.loop is not None and arg0 in func.loop.dep:
            func.loop.dep.append(str(ir._lvalue))
            func.loop.dep.append(tmp_node)
        return 

    else:
        raise Exception(arg0, " or/both ", arg1, " does not have a value or is Constant")

def parse_single_ir_low_level_call(ir, func):
    #External Call should returns a new tmp value
    #print("here low level call")
    func.Value_map[str(ir._lvalue)] = str(ir._lvalue)

    # record this as return value
    func.return_from_func[str(ir._lvalue)] = str(ir._function_name)
    return

def parse_single_ir_func_call(ir, func):
    #External Call should returns a new tmp value
    #func.Value_map[str(ir._lvalue)] = str(ir._lvalue)
    func.Value_map[str(ir._lvalue)] = str(ir._function_name)

    if func.loop is not None:
        func.Value_map[str(ir._lvalue)] = str(ir._function_name) + str(func.loop.iter)


    # record this as return value
    func.return_from_func[str(ir._lvalue)] = str(ir._function_name)
    #print("calling", str(ir._function_name), str(ir._destination))

    ### Assume all calls depends on intertor i
    if func.loop is not None:
        func.loop.dep.append(str(ir._lvalue))
        #print(("adding ", str(ir._lvalue) ,"to loop dep")
    
    ### oracle price function list
    oracle_functions = ["getAssetPrice", "getUnderlyingPrice", "getPrice"]
    if ir._function_name in oracle_functions:
        func.Price_dep.append(str(ir._lvalue))
        #print(("adding price dependencies", str(ir._lvalue)) 

    tname = ""
    tcontract = ""
    tfunc = ""
   
    if ir._function_name == tname:
        slither = func.slither
        contract = slither.get_contract_from_name(tcontract)
        func_call = None
        
        func_call = get_func_by_name(contract[0],tfunc)
        if func_call == None:
            raise Exception("Function name does not exist")
    
        input_args = func_call.parameters
        state_vars = contract[0].state_variables
        func_nodes = func_call.nodes

        func_obj = Func(tfunc, tname, func_nodes, input_args, state_vars, func_call, slither)

        analyze_func(func_obj)
        if len(func_obj.returns) == 1:
            func.Value_map[str(ir._lvalue)] = func_obj.returns[0]
        else:
            func.Value_map[str(ir._lvalue)] = func_obj.returns

        if len(func_obj.constraints) >= 0:
            func.constraints += func_obj.constraints

        #for value in func_obj.returns:
            #print(("#print(ing",value, value in func_obj.Price_dep)

        # add dependency
        func.Price_dep.append(str(ir._lvalue))

    if str(ir._lvalue) in func.Refs_map:
        raise Exception("Unhandled: function calls assigned to REF")
    return

def parse_single_ir_unpack(ir, func):
    lhs = str(ir._lvalue)
    rhs = str(ir.tuple)
    index = ir.index

    # assume only unpack function return results
    if rhs not in func.return_from_func:
        raise Exception("Unhandled: Unpack from non return value")
    if lhs not in func.Refs_map:

        #raise Exception("Unhandled: Unpack value to a non-REF variable", lhs)
        # add to value map
        func.Value_map[lhs] = lhs
        func.Refs_map[lhs] = lhs
    
    # now does nothing but only update func.loop.dep
    if rhs in func.Price_dep:
        func.Price_dep.append(lhs)
        func.Price_dep.append(func.Refs_map[lhs])
        #print(("updating dependencies", lhs)
       
    
    if func.loop is not None and rhs in func.loop.dep:
        func.loop.dep.append(lhs)
        func.loop.dep.append(func.Refs_map[lhs])
        func.Value_map[func.Refs_map[lhs]] = str(func.Refs_map[lhs]) +  "[" + str(func.loop.iter) + "]" 
        #print(("unpacking", rhs, lhs)

        ##print(("adding dependencies", Refs_map[lhs], func.loop.dep[rhs] )
    # update ValueMap 
    if isinstance(func.Value_map[rhs], list):
        func.Value_map[lhs] = func.Value_map[rhs][index]
        func.Value_map[func.Refs_map[lhs]] = func.Value_map[rhs][index]
    return

def parse_single_ir_unary(ir, func):
    lhs = str(ir._lvalue)
    variable = str(ir._variable)
    #print((lhs, variable, str(ir._type))
    if variable in func.Value_map:
        tmp_node = MathNode("", func.Value_map[variable], str(ir._type))
        func.Value_map[lhs] = tmp_node

        if variable in func.Price_dep:
            func.Price_dep.append(lhs)
            func.Price_dep.append(tmp_node)
        
        if func.loop is not None and variable in func.loop.dep:
            func.loop.dep.append(variable)
    else:
        raise Exception("Unary operation variable not in Value Map")

def parse_single_ir_binary(ir, func):
    lhs = str(ir._variables[0])
    rhs = str(ir._variables[1])

    #print("Binary", lhs, rhs, lhs in func.Price_dep, rhs in func.Price_dep)
    if lhs in func.Value_map and rhs in func.Value_map:
        v1 = func.Value_map[lhs]
        v2 = func.Value_map[rhs]
        #print(("inside binaray two ops: ", v1, v2)
        tmp_node = MathNode(v1, v2, ir.type)

        if str(ir._lvalue) == str(lhs) and str(ir.type) == '+' and func.loop is not None:
            tmp_node = AccNode(str(lhs), v2, func.loop.lower_bound, func.loop.upper_bound, func.loop.iter)
            #print(("ACC", tmp_node)
            
            
        # return a tmp variable 
        func.Value_map[str(ir._lvalue)] = tmp_node

        if str(ir._lvalue) in func.Refs_map:
            func.Value_map[func.Refs_map[str(ir._lvalue)]] = tmp_node

        # if both operands depend on the same variable
        # update the dependency list
        
        if BinaryType.return_bool(ir.type):
            ##print(("Binary type is bool")
            
            if lhs in func.Price_dep or rhs in func.Price_dep:
                #print(("updating price dependencies", str(ir._lvalue) )
                func.Price_dep.append(str(ir._lvalue))
                func.Price_dep.append(tmp_node)
        else:
            if lhs in func.Price_dep or rhs in func.Price_dep:
                #print(("updating price dependencies", str(ir._lvalue) )
                func.Price_dep.append(str(ir._lvalue))
                func.Price_dep.append(tmp_node)
                if str(ir._lvalue) in func.Refs_map:
                    #print(("inside Binary", func.Refs_map[str(ir._lvalue)])
                    func.Price_dep.append(func.Refs_map[str(ir._lvalue)])

        # if both operands depend on the same variable
        # update the dependency list
        
        if func.loop is not None and (v1 in func.loop.dep or v2 in func.loop.dep):
            func.loop.dep.append(str(ir._lvalue))
            func.loop.dep.append(tmp_node)
  
        return 

    if (lhs in func.Value_map and isinstance(ir._variables[1], Constant)):     
        
        tmp_node = MathNode(func.Value_map[lhs], rhs, ir.type)
        # record the tmp value
        func.Value_map[str(ir._lvalue)] = tmp_node
        # update dependencies
        if (lhs in func.Price_dep):
            func.Price_dep.append(str(ir._lvalue))
            func.Price_dep.append(tmp_node)

        if func.loop is not None and lhs in func.loop.dep:
            func.loop.dep.append(str(ir._lvalue))
            func.loop.dep.append(tmp_node)
        return  

    if (rhs in func.Value_map and isinstance(ir._variables[0], Constant)):      
        tmp_node = MathNode(lhs, func.Value_map[rhs], ir.type)
        # record the tmp value
        func.Value_map[str(ir._lvalue)] = tmp_node
        # update dependencies

        if (rhs in func.Price_dep):
            func.Price_dep.append(str(ir._lvalue))
            func.Price_dep.append(tmp_node) 

        if func.loop is not None and rhs in func.loop.dep:
            func.loop.dep.append(str(ir._lvalue))
            #print(("updating depencies in Binary",str(ir._lvalue) )
            func.loop.dep.append(tmp_node) 

        return

    if (isinstance(ir._variables[0], Constant) and isinstance(ir._variables[1], Constant)):
        tmp_node = MathNode(lhs, rhs, ir.type)
        func.Value_map[str(ir._lvalue)] = tmp_node
        func.Price_dep.append(str(ir._lvalue))
        func.Price_dep.append(tmp_node)
        if func.loop is not None:
            func.loop.dep.append(str(ir._lvalue))
            func.loop.dep.append(tmp_node)
    '''   
    else:
        raise Exception("BAD some unhandled case")
    '''

def parse_single_ir_convert(ir, func):
    # temp value should has the same dependency as the input
    # TMP_# = convert var type
    
    lhs = str(ir._lvalue)
    rhs = str(ir._variable)
    #print("CONVERT", lhs, rhs)
    if func.loop is not None and rhs in func.loop.dep:
        func.loop.dep.append(lhs)
    
    func.Value_map[lhs] = func.Value_map[rhs] if rhs in func.Value_map else str(rhs)
    func.return_from_func[lhs] = lhs

def parse_single_ir_InternalCall(ir, func):
    # TODO: Better naming of the variable
    # for internal call name the tmp variable as the function name
    #print("ir internal func call", str(ir._function_name))
    func.Value_map[str(ir._lvalue)] = str(ir._function_name)
    if func.loop is not None:
        func.Value_map[str(ir._lvalue)] = str(ir._function_name) + "[" + str(func.loop.iter) + "]"
    # record this as return value
    func.return_from_func[str(ir._lvalue)] = ir._function_name
    #print((ir._function_name)
    #print(("adding ", str(ir._lvalue), "to return of func")
    if func.loop is not None:
        func.loop.dep.append(str(ir._lvalue))

    oracle_functions = ["getPriceInternal","getPriceUSDCETH", "getPriceOfToken", "_assetLiquidityData", "_assetData"]
    
    if ir._function_name in oracle_functions:
        func.Price_dep.append(str(ir._lvalue))
        return

    internal_contract = ""
    internal_func_name = []

    # internal_func_name: functions containing critical computation
    # internal_contract: contrac that the function belongs to
    if TEST_CASE == "compound":
        internal_func_name = ["getHypotheticalAccountLiquidityInternal"]
        internal_contract = "ComptrollerG3"
    elif TEST_CASE == "testamm":
        internal_func_name = ["maxBorrowAmount"]
        internal_contract = "SimpleLender"

    if str(ir._function_name) in internal_func_name:
        slither = func.slither
        contract = slither.get_contract_from_name(internal_contract)
        func_call = get_func_by_name(contract[0], ir._function_name)
        if func_call == None:
            raise Exception("Function name does not exist")

        input_args = func_call.parameters
        state_vars = contract[0].state_variables
        func_nodes = func_call.nodes
        #print((len(func_nodes))

        func_obj = Func(internal_contract, ir._function_name, func_nodes, input_args, state_vars, func_call, slither)
        if func.loop is not None:
            func_obj.loop = func.loop
        analyze_func(func_obj)
        if len(func_obj.returns) == 1:
            func.Value_map[str(ir._lvalue)] = func_obj.returns[0]
            #print(("after internal call: ", str(ir._lvalue), func_obj.returns[0])
        else:
            func.Value_map[str(ir._lvalue)] = func_obj.returns
        for value in func_obj.returns:
            if value in func_obj.Price_dep:
                func.Price_dep.append(str(ir._lvalue))
                func.Price_dep.append(value)


def parse_single_ir_SolidityCall(ir, func):
    #print("Entering a solidty Call")
    #print(ir)
    if ir.function.name == "require(bool,string)":        
        #print(("inside require:" , str(ir.arguments[0]))
        bool_expr = ir.arguments[0]
        if str(bool_expr) in func.Price_dep:
            func.constraints.append(Constraint(func.Value_map[str(bool_expr)]))

def parse_single_ir_Return(ir, func):
    #print(("inside Return: ", ir)
    for value in ir._values:
        if str(value) in func.Value_map:
            #print(("returning", func.Value_map[str(value)])
            func.returns.append(func.Value_map[str(value)])
        else:
            #print(("returning", value)
            func.returns.append(str(value))

def parse_single_ir_length(ir, func):
    lhs = str(ir._lvalue)
    if lhs in func.Refs_map:
        func.Refs_map[lhs] = str(ir._value) + ".length"
        func.Value_map[func.Refs_map[lhs]] = str(ir._value) + ".length"
    func.Value_map[lhs] = str(ir._value) + ".length"

def parse_single_ir_libraryCall(ir, func):
    # TODO: HANDLE library calls
    return

def parse_single_ir_enumerable(ir, func):
    lhs = str(ir._lvalue)
    #print("Enumerable library: ", ir)    
    arg = str(ir._arguments[0])
    if arg in func.Refs_map:
        arg = func.Refs_map[arg]
    # should return a tmp variable:
    func.Value_map[lhs] = str(arg) + str(ir._function_name)
    if str(ir._function_name) == "at":
        func.return_from_func[lhs] = lhs

def parse_node_irs(node, func):    
    for ir in node.irs:
        if isinstance(ir, Assignment):
            parse_single_ir_assign(ir, func)
        elif isinstance(ir, Member):
            parse_single_ir_memebr(ir, func)
        elif isinstance(ir, Index):
            parse_single_ir_index(ir, func)
        elif isinstance(ir, HighLevelCall):
            if ir.destination == "SafeMath":
                parse_single_ir_safe_math(ir, func)
            elif ir.destination == "EnumerableSetUpgradeable":
                parse_single_ir_enumerable(ir, func)
            else:
                parse_single_ir_func_call(ir, func)
        elif isinstance(ir, Unpack):
            parse_single_ir_unpack(ir, func)
        elif isinstance(ir, Unary):
            parse_single_ir_unary(ir, func)
        elif isinstance(ir, Binary):
            parse_single_ir_binary(ir, func)
        elif isinstance(ir, TypeConversion):
            parse_single_ir_convert(ir, func)
        elif isinstance(ir, SolidityCall):
            parse_single_ir_SolidityCall(ir, func)
        elif isinstance(ir, InternalCall):
            parse_single_ir_InternalCall(ir, func)
        elif isinstance(ir, Return):
            parse_single_ir_Return(ir, func)
        elif isinstance(ir, LowLevelCall):
            parse_single_ir_low_level_call(ir, func)
        elif isinstance(ir, Length):
            parse_single_ir_length(ir, func)
        elif isinstance(ir, LibraryCall):
            parse_single_ir_libraryCall(ir, func)


def get_func_by_name(contract, func_name):
    for func in contract.functions:
        if str(func.name) == func_name:
            #print(len(func.nodes))
            return func

    return None

def analyze_func(func):
    # Intialize 
    global LOOP_COUNT
    for arg in func.input_args:
        func.Value_map[arg.name] = arg.name

    for arg in func.state_vars:
        func.Value_map[arg.name] = arg.name

    for node in func.nodes:
        if node.type == NodeType.EXPRESSION:
            if len(node._fathers) == 1 and node._fathers[0].type == NodeType.IF:
                # do if else detection
                father = node._fathers[0]
                if len(father._sons) == 2:
                    if father._sons[0].type == NodeType.EXPRESSION and father._sons[1].type == NodeType.EXPRESSION:
                        #print("If Else detected:", node.node_id)
                        func.flagif = True
                        func.flagcount += 1
            parse_node_irs(node, func)
            func.flagif = False

        elif node.type == NodeType.IFLOOP:
            lhs = node.expression._expressions[0]
            rhs = node.expression._expressions[1]
            loop_iter = str(lhs)
            #print("loop", rhs)
            bound = func.Value_map[str(rhs)] if str(rhs) in func.Value_map else str(rhs)
            loop = Loop(func.name, loop_iter, '0', bound)
            LOOP_COUNT = LOOP_COUNT + 1
            # loop iter remains as a symbol i = i
            func.Value_map[loop_iter] = loop_iter
            func.loop = loop
        elif node.type == NodeType.VARIABLE:            
            var_name = str(node.variable_declaration)
            # #print(("adding new variable: ", var_name)
            # a varaible is consider symbolic
            func.Value_map[var_name] = var_name
            parse_node_irs(node, func)
            if func.Value_map[var_name] == "0":
                func.Value_map[var_name] = var_name
            
        elif node.type == NodeType.IF:
            for ir in node.irs:
                if isinstance(ir, Condition):
                    #print("Condition node")
                    continue
            continue
        elif node.type == NodeType.ENDLOOP:
            #print(node.type)
            continue
            
        elif node.type == NodeType.RETURN: 
            parse_node_irs(node, func)   
        else:
            #print(node.type)
            # Ignore other types of ir for now
            continue
    
    if len(func.constraints) > 0: 
        for const in func.constraints:
            print("===============================")
            print(const)
            print("===============================")
            CONST_LIST.append(str(const))

    
    return 

def stats():
    start_time = time.time()
    vars_list = []
    vars_map = {}
    loop_iter = None
    constraints = []
    reserved_token = ['(', ')', 'SUM', 'mul', 'div', 'add', 'sub', 'from', 'to', '**', "{", "}", "=", ">=" ,"!", "<=", ">", "<", "\\", "/", "*", "-", "+", "!="]
    for l in CONST_LIST:
        if l.startswith("("):
            l = l.replace("add", "+")
            l = l.replace("mul", "*")
            l = l.replace("div", "/")
            l = l.replace("sub", "-")
            constraints.append(l)

    
    var_list = []
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
                    var_list.append(token)
                    vars_map[token] = token
                    #innermost_brackets = re.findall("\([^\(]*?"+ token + "[\s]*?\)", sum_str)
                    #print(innermost_brackets)
                    #sum_str = sum_str.replace(token, "0")
                    
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

    vars_vec = set(vars_vec)
    var_list = set(var_list)
    print("Number of vector variables: ", len(vars_vec))
    print("Number of scalar variables: ", len(var_list))
    print("Number of requires: ", len(set(constraints)))
    f = open("output.log", "a")
    f.write(" Number of vector variables: %d " % len(vars_vec))
    f.write(" Number of scalar variables: %d" % len(var_list))
    f.write(" Number of requires: %d\n" % len(set(constraints)))
    f.close()


def test(test_name):
    global TEST_CASE
    global CONST_LIST

    contract_name = ""
    contract_func = ""
    sol_file = ""

    # add a new contract
    # test_name: contract name, command line argument
    # contract_name: contract which entry function belongs to
    # contract_func: entry function
    # sol_file: path to the source code
    if test_name == "compound":
        contract_name = "ComptrollerG3"
        contract_func = "borrowAllowed"
        sol_file = "./benchmark/compound.sol"
        TEST_CASE = "compound"

    elif test_name == "testamm":
        contract_name = "SimpleLender"
        contract_func = "borrowETH"
        sol_file = "./benchmark/testamm.sol"
        TEST_CASE = "testamm"
    
    start_time = time.time()
    slither = Slither(sol_file)
    ctime = time.time() - start_time
    print("Done compiling --- %s seconds ---" % (ctime))
    myContract = slither.get_contract_from_name(contract_name)

    
    # if get_func_by_name doesn't work,
    # try: func_call = contract[0].get_function_from_signature("func_signature")
    func = get_func_by_name(myContract[0], contract_func)

    if func is None:
        raise Exception("Function name does not exist ", contract_func)
    
    input_args = func.parameters
    state_vars = myContract[0].state_variables
    func_nodes = func.nodes

    func_obj = Func(contract_func, contract_name, func_nodes, input_args, state_vars, func, slither)

    analyze_func(func_obj)

    end_time = time.time() - start_time
    print("Done summarizing --- %s seconds ---" % (end_time))
    print("Number of loops encountered: ", LOOP_COUNT)

    f = open("output.log", "a")
    f.write("Test case: %s "  % TEST_CASE)
    f.write(" Number of Loops Encountered --- %d ---" % LOOP_COUNT)
    f.write(" Compilation Time --- %s seconds ---" % (ctime))
    f.write(" Total Execution Time --- %s seconds ---" % (end_time))
    f.close()

    stats()
    


TEST_CASE = ""
CONST_LIST = []
LOOP_COUNT = 0

def main(args):
    test(args.contract)    

if __name__ == '__main__':
    assert len(argv) > 1
    args = parse_args()    
    main(args)
