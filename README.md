### Applying OVer On A New Contract
This repo contains two end-to-end examples (testAMM, Compound) and gives you guidelines on how to apply OVer to a new test case. 

##### Setup
Install the OVer VM and change to the `~/icse-experiment` directory.
Activate the python environment `venv`.
Download `DEMO` and move it to the `~/icse-experiment` directory. 

##### Guidelines
*Step 1*: OVer input (similar to Slither) must be a single file, thus, all the protocol source code along with its dependencies including all functions and contracts of interest must be put into a single file. It is necessary that Slither can successfully compile this file since Over builds on it. 

- The source code of the two examples is under `DEMO/benchmark/`.
- The source code might need modifications in the following cases:
    - Constraint is not specified by a `require` statement (see examples in `compound.sol`). 
    - OVer currently only supports math expressions written with SafeMath or binary operators (+,-,*,/). You might need to simplify the source code if the contract uses other math libraries. 

*Step 2*: Create a new test case by specifying the entry point, in function **test** of `summary_generator.py`. Identify the functions containing critical computations and the oracle price getter function in the contract; add this information to `parse_single_ir_InternalCall` or `parse_single_ir_func_call`, depending on the function's type. OVer will extract a summary for these functions, avoiding leaving them as free variables, and perform oracle dependency analysis based on the specified getter function.

- Example *testAMM*: The function that implements the verification logic of borrow action is **borrowETH**. We mark it as the entry point of our analysis in `test`.
Since **borrowETH** calls an internal function **maxBorrowAmount** to compute the maximum allowance, we tell OVer to analyze this function in `parse_single_ir_InternalCall`, where we also specify the oracle getter is named **getPriceUSDCETH**. 
- Example *Compound*: The function that contains `require` statements is **borrowAllowed**, which serves as the entry point of our analysis.  **getHypotheticalAccountLiquidityInternal** contains the calculation of the user's position and involves a loop. Add this function to `parse_single_ir_InternalCall` and OVer will compute a summary of the loop and incorporate it into the constraint summary. Note that OVer automatically detects loops and performs loop summary. No further modification is needed for contracts with loops. Oracle price getter is called **getUnderlyingPrice**. This information is added to the functions that handle function calls. 
- Check the implementation of `parse_single_ir_InternalCall` and `test` and you can see where to specify the function names. 
 
*Step 3*: Run the summary generator and the constraints extracted will be displayed. Run `convert_v1.py` to generate a python script that proves if the constraints can be satisfied given an oracle deviation. You can customize the script to solve optimization problems of interest. 

Example testAMM: 
```sh
python3.8 summary_generator_v1.py --contract testamm
```
Expected output in the terminal:
```sh
Done compiling --- 0.19291901588439941 seconds ---
===============================
( amount <= ( ( ( ( USDCdeposits[msg.sender] * getPriceUSDCETH )  / 1000000000000000000 )  * collateralizationRatio )  / 10000 )  ) 
===============================
Done summarizing --- 0.19315195083618164 seconds ---
Number of loops encountered:  0
Number of vector variables:  0
Number of scalar variables:  4
Total number of constraints extracted:  1
```
Copy the constraint(s) to a text file. `./DEMO/testamm.txt` contains the constraint extracted for testAMM. Run `convert_v1.py` and it will generate a python script named `generated_testamm.py`.
```sh
python3.8 convert_v1.py --contract testamm
```
Run the generated script.
```sh
python3.8 generated_testamm.py
```
To test compound, run 
```sh
python3.8 summary_generator_v1.py --contract compound
```
You can verify that the displayed constraint is the same as `./DEMO/compound.txt`. Now convert the constraint to a python script with 
```sh
python3.8 convert_v1.py --contract compound
```
and you can run the generated script.
```sh
python3.8 generated_compound.py
```
Note that for both cases, **z3** will find a counter-example, indicating that the property does not hold given the oracle deviation. Customize the script to solve the optimization problem of interest.



