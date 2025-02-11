'''
conftest.py is a configuration file automatically accessed by pytest
any @pytest.fixture created here is available to any other test file
if they reference it as a parameter.
'''

import pytest, re, sys, os, json, traceback, multiprocessing, pickle, inspect
from io import StringIO


# ================
# GLOBAL VARIABLES
# ================

# Enter the name of the file to be tested here, but leave out the .py file extention.
solution_module = "a6_solution_function_smorgasbord"
student_module = "a6_function_smorgasbord"

# for this test, there are 2 files, so adding 2 extra globals
solution_functions_module = "a6_solution_my_functions"
student_functions_module = "a6_my_functions"

def detect_module(solution_module, student_module):
    if os.path.exists(f"{solution_module}.py"):
        return solution_module
    elif os.path.exists(f"{student_module}.py"):
        return student_module
    else:
        return "PATH NOT FOUND"

#default_module_to_test = "a6_function_smorgasbord"#detect_module(solution_module, student_module)
default_module_to_test = detect_module(solution_module, student_module)
functions_module_to_test = detect_module(solution_functions_module, student_functions_module)

# default per-test-case timeout amount in seconds:
default_timeout_seconds = 6

# Path to the directory containing this file
CURRENT_DIR = os.path.dirname(__file__)

# ========
# FIXTURES
# ========

@pytest.fixture
def test_cases():
    # Path to the final captured test cases JSON file
    captured_test_cases_file = os.path.join(CURRENT_DIR, 'test_cases_final.json')
    
    # Load the test cases
    with open(captured_test_cases_file, 'r') as f:
        test_cases = json.load(f)
    
    return test_cases

# =====
# HOOKS
# =====

# Global set to track which tests have been run
_run_tests = set()

# Hook that runs before each test is executed
@pytest.hookimpl(tryfirst=True)
def pytest_runtest_call(item):
    """
    I sometimes use this in testing to make sure tests work regardless of the order
    they are run in. Currently not called
    """
    test_name = item.nodeid  # Get the test's identifier (e.g., file path + test name)
    
    if test_name not in _run_tests:
        print(f"First time running {test_name}")
        _run_tests.add(test_name)
    else:
        print(f"{test_name} has already been run in this session")


def pytest_sessionfinish():
    """
    This is a keyword name of a function for pytest.
    It will run automatically when done with
    a session of pytest. I used to have cleanup logic here, but
    after refactoring it was no longer necessary. If I need cleanup
    again, place logic here.
    """
    pass


# ================
# HELPER FUNCTIONS
# ================

import importlib

def get_function(module_name, func_name):
    """
    Try to import the function from a module with various naming conventions.
    """
    function_variations = [
    func_name,  # snake_case
        func_name.title().replace("_", ""), # PascalCase
        (func_name[0].lower() + func_name.title()[1:]).replace("_", ""),    # camelCase
    ]

    module = importlib.import_module(module_name)
    
    for variation in function_variations:
        if hasattr(module, variation):
            return getattr(module, variation)
    
    raise AttributeError(f"Function '{func_name}' not found in {module_name}.")

def is_picklable(obj):
    """
    Each test case is run in a subprocess, with relevant info/variables
    Sent back to the main process through a Queue. Because that requires
    pickling the data, this is used to check if something I'm trying to send
    is actually able to be pickled before I actually send it.
    """

    try:
        pickle.dumps(obj)
    except Exception:
        return False
    else:
        return True

def load_student_code(inputs, test_case=None, module_to_test=default_module_to_test,
                      function_tests=None):
    """
    Loads the student's code in a subprocess with mocked inputs to prevent hanging the main test process.
    """
    try:
        # Create a queue to communicate with the subprocess
        queue = multiprocessing.Queue()

        # Start the subprocess
        p = multiprocessing.Process(target=_load_student_code_subprocess, args=(queue, inputs, test_case, module_to_test, function_tests))
        p.start()

        # Wait for the subprocess to finish, or continue if the timeout limit is reached
        p.join(default_timeout_seconds)

        if p.is_alive():
            # Subprocess is still running; terminate it
            p.terminate()
            p.join() # makes sure the main program waits for the subprocess to fully terminate
            
            # Handle timeout
            pytest.fail(timeout_message_for_students(test_case))
        else:
            # Subprocess finished; get the result
            if not queue.empty():
                status, payload = queue.get()
                if status == 'success':
                    # get input prompts, printed messages and all other variables from the queue
                    captured_input_prompts, captured_output, module_globals, function_results = payload
                    return captured_input_prompts, captured_output, module_globals, function_results
                elif status == 'exception':
                    exception_data = payload  # Exception data dictionary
                    exception_message_for_students(exception_data, test_case)
                else:
                    pytest.fail("Unexpected status from subprocess. Contact your professor.")
            else:
                pytest.fail("Subprocess finished without returning any data. Contact your professor")
    except Exception as e:
        exception_message_for_students(e, test_case)


def _load_student_code_subprocess(queue, inputs, test_case, module_to_test, function_tests):
    """
    Called in load_student_code as a subprocess, which allows it to 
    be terminated if the student's code hangs. Student code is run through
    exec(). Before that, a mock input function is created to replace the
    actual input function, StringIO captures printed messages, and if the
    student has a "main" function, it also will capture local variables there
    for any test that assumes the existence of global variables.
    """

    try:
        # Prepare the mocked input function and capture variables
        captured_input_prompts = []
        input_iter = iter(inputs)
        
        def mock_input(prompt=''):
            if prompt == '':
                return ''
            else:
                captured_input_prompts.append(prompt)
            try:
                
                return next(input_iter)
            except StopIteration:
                # Handle the case where there are more input() calls than provided inputs
                raise
        
        # Prepare the global namespace for exec()
        globals_dict = {
            '__name__': '__main__',  # Ensures that the if __name__ == '__main__' block runs
            'input': mock_input,     # Overrides input() in the student's code
        }

        # Prepare to capture 'main' function's locals
        main_locals = {}

        # this creates a way for tracking any variables created in a "main" function
        # if they write their code that way instead of having everything at the global level.
        def trace_calls(frame, event, arg):
            if event != 'call':
                return
            code = frame.f_code
            func_name = code.co_name
            if func_name == 'main':
                # We are entering the 'main' function
                def trace_lines(frame, event, arg):
                    if event == 'return':
                        # We are exiting 'main', capture locals
                        main_locals.update(frame.f_locals)
                    return trace_lines
                return trace_lines
            return

        # Set the trace function
        sys.settrace(trace_calls)
        
        # Redirect sys.stdout to capture print statements
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        # Read the student's code from the file
        module_file_path = module_to_test + '.py'
        with open(module_file_path, 'r', encoding='utf-8', errors='replace') as f:
            code = f.read()

        # Execute the student's code within the controlled namespace
        exec(code, globals_dict)

        # Remove the trace function
        sys.settrace(None)

        # Capture the output printed by the student's code
        captured_output = sys.stdout.getvalue()
        
        # Reset sys.stdout
        sys.stdout = old_stdout
        
        if function_tests:
            function_results = test_functions(function_tests, globals_dict)
        else:
            function_results = {"No functions tested": "No functions tested"}

        # Collect global variables from the student's code
        module_globals = {k: v for k, v in globals_dict.items() if is_picklable(v)}

        # Add main_locals to module_globals under a special key
        module_globals['__main_locals__'] = main_locals
        
        # Send back the results
        queue.put(('success', (captured_input_prompts, captured_output, module_globals, function_results)))
        
    except StopIteration as e:
        # Reset sys.stdout in case of exception
        sys.stdout = old_stdout
        sys.settrace(None)
        # Send the exception back as a dictionary
        exc_type, exc_value, exc_tb = sys.exc_info()
        test_case_inputs = '\n'.join(test_case["inputs"])
        exception_data = {
            'type': type(e).__name__,
            'message': (f"{str(e)}\n\nHOW TO FIX IT:\n\nThis error was very likely caused by your code asking for more input() calls than the test case expected. "
                        f"To see where this is happening in your code, run your code and input THESE EXACT INPUTS IN THIS ORDER:\n\n"
                        f"{test_case_inputs}\n\n"
                        f"If, after entering those exact inputs in that order, your code asks for another input, THAT is the cause of this error. "
                        f"Make it so your code doesn't ask for any more inputs after the last input entered. If you believe that is a mistake, please "
                        f"reach out to your professor."),
            'traceback': traceback.format_exception(exc_type, exc_value, exc_tb)
        }
        queue.put(('exception', exception_data))
    
    except EOFError as e:
        # Reset sys.stdout in case of exception
        sys.stdout = old_stdout
        sys.settrace(None)
        # Send the exception back as a dictionary
        exc_type, exc_value, exc_tb = sys.exc_info()
        exception_data = {
            'type': type(e).__name__,
            'message': (f"{str(e)}\n\nThis was most likely caused by an input() function being present "
                        f"in a .py module that you imported. Please only use the input() function in the main assignment .py file."),
            'traceback': traceback.format_exception(exc_type, exc_value, exc_tb)
        }
        queue.put(('exception', exception_data))

    except FileNotFoundError as e:
        # Reset sys.stdout in case of exception
        sys.stdout = old_stdout
        sys.settrace(None)
        # Send the exception back as a dictionary
        exc_type, exc_value, exc_tb = sys.exc_info()
        exception_data = {
            'type': type(e).__name__,
            'message': str(e),
            'traceback': traceback.format_exception(exc_type, exc_value, exc_tb)
        }
        queue.put(('exception', exception_data))
    except BaseException as e:
        # Reset sys.stdout in case of exception
        sys.stdout = old_stdout
        sys.settrace(None)
        # Send the exception back as a dictionary
        exc_type, exc_value, exc_tb = sys.exc_info()
        exception_data = {
            'type': type(e).__name__,
            'message': str(e),
            'traceback': traceback.format_exception(exc_type, exc_value, exc_tb)
        }
        queue.put(('exception', exception_data))

def get_custom_functions_from_module(module):
    """
    Given a module object, return a dictionary of all custom functions defined in the module.
    """
    return {name: obj for name, obj in vars(module).items() if inspect.isfunction(obj)}

def is_user_defined_module(module):
    """
    Determines if a module is user-defined by checking if it resides in the student's directory.
    Excludes standard library and external packages.
    """
    module_path = getattr(module, '__file__', '')
    if module_path:  # Only proceed if the module has a __file__ attribute
        base_dir = os.path.dirname(os.path.realpath(module_path))  # Get the directory of the module
        # Compare to standard library or third-party package paths
        return not base_dir.startswith(sys.prefix)  # Exclude standard library and packages
    return False

def get_all_custom_functions(globals_dict):
    """
    Retrieve all custom functions defined within the student's code and any user-defined modules
    they import. Excludes functions from external libraries like random, numpy, etc.
    """
    custom_functions = {}
    
    # First, collect all custom functions defined in the main file
    for name, obj in globals_dict.items():
        if inspect.isfunction(obj):
            # Only include functions defined in the student's main file (__main__) or other files
            if obj.__module__ == '__main__' or is_user_defined_module(sys.modules[obj.__module__]):
                if name != 'input':  # this just exlcudes the mocked input function run during the tests.
                    custom_functions[name] = obj

    # Now, check for any imported modules in the globals_dict
    for name, obj in globals_dict.items():
        if inspect.ismodule(obj) and is_user_defined_module(obj):
            # Add custom functions from this imported module
            custom_functions.update(get_custom_functions_from_module(obj))

    return custom_functions

def test_functions(function_tests, globals_dict):

    function_results = {}

    if not function_tests:
        function_results["FUNCTION ERROR"] = "No functions were provided to function_tests. Send a message your professor."
        return function_results

    all_custom_functions = get_all_custom_functions(globals_dict)
    all_custom_functions_names = [key for key in all_custom_functions]
    all_custom_functions_names = '\n'.join(all_custom_functions_names)


    for func_name_original, test_cases in function_tests.items():

        function_variations = [
            func_name_original,  # snake_case
            func_name_original.title().replace("_", ""),  # PascalCase
            (func_name_original[0].lower() + func_name_original.title()[1:]).replace("_", ""),  # camelCase
        ]


        # check if function name in in the globals:
        func_found = False
        for func_variation in function_variations:
            if func_variation in all_custom_functions:
                func_found = True
                student_func = all_custom_functions[func_variation]
                break
        
        # if the function wasn't found, just return with an error.
        if not func_found:
            function_results["FUNCTION ERROR"] = (f"This test is looking specifically for the function:\n\n{func_name_original}\n\n"
                                                  f"But it couldn't find it, nor any of its accepted variations:\n\n{function_variations[1]}, {function_variations[2]}\n\n"
                                                  f"Make sure you are spelling the function name correctly. Below are all of "
                                                  f"the functions you made in your code that the test could find:\n\n"
                                                  f"{all_custom_functions_names}")
            return function_results

        # Run the function with the provided arguments
        if callable(student_func):
            for test_case in test_cases:
                # add a list for the value in the results dictionary if it isn't there yet,
                # and once it is there, append the results of calling the function 
                print(test_case[0])
                function_results.setdefault(func_name_original, []).append(student_func(*test_case[0]))
        else:
            function_results["FUNCTION ERROR"] = f"{func_variation} was found in your code, but it isn't callable as a function. Make sure you defined the function correctly."
            return function_results
    
    return function_results


def normalize_text(text):
    """
    Used by tests that look for specific output or input prompts.
    Makes all text lowercase, reduces all spacing to just one space
    and removes any extra symbols, except for negative signs and decimals
    associated with numbers.
    """
    if isinstance(text, str):
        # Lowercase the input
        text = text.lower()
        
        # Replace newlines with a single space
        text = text.replace('\n', ' ')
        
        # Replace multiple spaces with a single space
        text = re.sub(r'\s+', ' ', text)
        
        # Remove periods not between digits
        text = re.sub(r'(?<!\d)\.(?!\d)', '', text)
        
        # If there is any character followed by a colon : other than a space, add a space
        text = re.sub(r'(:)(\S)', r'\1 \2', text)
    
        # Remove all other punctuation and symbols
        text = re.sub(r'[!"#$%&\'()*+,/:;<=>?@\[\]^_`{|}~]', '', text)
        
        # Temporarily replace negative signs with a placeholder
        text = re.sub(r'((?<=^)|(?<=\s))-(?=\d)', 'NEG_SIGN_PLACEHOLDER', text)
        
        # Replace remaining hyphens (e.g., between numbers) with a space
        text = text.replace('-', ' ')
        
        # Replace multiple spaces again in case punctuation removal created extra spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Restore negative signs
        text = text.replace('NEG_SIGN_PLACEHOLDER', '-')
        
        # Strip leading and trailing spaces
        return text.strip()
    else:
        return text

#74 characters should be the max
def format_error_message(custom_message: str = None,
                         test_case: dict = None,
                         display_inputs: bool = False,
                         display_input_prompts: bool = False,
                         display_invalid_input_prompts: bool = False,
                         display_printed_messages: bool = False,
                         display_invalid_printed_messages: bool = False,
                         line_length: int = 74) -> str:
    """
    Constructs the main error students will see in the Test Results window.
    The main purpose in the error message is to communicate which test case
    a test failed on, and then optionally include extra details that might
    help out the student
    """
    
    # some starting strings. All messages will be appended to error_message
    error_message = ''
    divider = f"\n{"-"*line_length}\n"
    error_message += divider
    error_message += f"IS 303 STUDENTS: READ THE ERROR MESSAGES IN RED BELOW\n\n"
    error_message += "↓"*line_length + "\n"
    if test_case:
        error_message += divider
        error_message += f"TEST FAILED DURING TEST CASE: {test_case["id_test_case"]}"
        error_message += divider
        error_message += insert_newline_at_last_space((
            f"\nLook at the \"Test Cases\" section of the instructions in README.md. "
            f"Run your code while inputting the EXACT inputs shown there to see where/why "
            f"your code either breaks or doesn't pass this test.\n\n"
        ), line_length)
        test_case_description = f"FOR TEST CASE: {test_case["id_test_case"]}"
    else:
        test_case_description = ''

    if custom_message:
        error_message += divider
        error_message += f"WHAT WENT WRONG:"
        error_message += divider
        error_message += insert_newline_at_last_space("\n" + custom_message, line_length)

    if display_inputs:
        inputs_concatenated = '\n'.join(test_case["inputs"])
        error_message += divider
        error_message += f"INPUTS ENTERED {test_case_description}"
        error_message += divider
        error_message += insert_newline_at_last_space(f"\nThese inputs will be entered in this exact order during this test case:\n\n\n", line_length)
        error_message += inputs_concatenated + "\n"

    if display_input_prompts:
        expected_input_prompts_concatenated = '\n'.join(test_case["input_prompts"])
        error_message += divider
        error_message += f"EXPECTED INPUT PROMPTS {test_case_description}"
        error_message += divider
        error_message += insert_newline_at_last_space(f"\nThese inputs prompts must appear at least once during this test case:\n\n\n", line_length)
        error_message += expected_input_prompts_concatenated + "\n"

    if display_invalid_input_prompts:
        invalid_input_prompts_concatenated = '\n'.join(test_case["invalid_input_prompts"])
        error_message += divider
        error_message += f"INVALID INPUT PROMPTS {test_case_description}"
        error_message += divider
        error_message += insert_newline_at_last_space(f"\nThe test will fail if any of the following appear during this test case:\n\n\n", line_length)
        error_message += invalid_input_prompts_concatenated + "\n"

    if display_printed_messages:
        expected_printed_messages_concatenated = '\n'.join(test_case["printed_messages"])
        error_message += divider
        error_message += f"EXPECTED PRINTED MESSAGES {test_case_description}"
        error_message += divider               
        error_message += insert_newline_at_last_space(f"\nThese printed messages must appear at least once during this test case:\n\n\n", line_length)
        error_message += expected_printed_messages_concatenated + "\n"

    if display_invalid_printed_messages:
        invalid_printed_messages_concatenated = '\n'.join(test_case["invalid_printed_messages"])
        error_message += divider
        error_message += f"INVALID PRINTED MESSAGES {test_case_description}"
        error_message += divider
        error_message += insert_newline_at_last_space(f"\nThe test will fail if any of the following appear during this test case:\n\n\n", line_length)
        error_message += invalid_printed_messages_concatenated + "\n"

    error_message += "\n"

    return error_message

def insert_newline_at_last_space(s, width=74):
    """
    Because pytest fail messages have a specific width they are printed at,
    if I don't format my own error messages at that same width, they
    look much worse. This just adds in a new line before the width limit
    is hit for any string that you pass to it.
    """

    lines = []
    current_line = ""
    
    for char in s:
        current_line += char
        
        # If we hit a newline, append the current line and reset the line
        if char == '\n':
            lines.append(current_line.strip())  # Add the line and strip any extra spaces
            current_line = ""
            continue
        
        # If the current line exceeds the width, break at the last space
        if len(current_line) > width:
            # Find the last space before the width limit
            break_index = current_line.rfind(' ', 0, width)
            
            # If no space is found, break at the width limit
            if break_index == -1:
                break_index = width
            
            # Append the part of the line before the break
            lines.append(current_line[:break_index].strip())
            
            # Reset current_line to the remaining unprocessed part of the string
            current_line = current_line[break_index:].lstrip()  # Remove leading spaces in the next line
            
    # Append the last part of the string (if any)
    if current_line:
        lines.append(current_line.strip())
    
    return '\n'.join(lines)

def exception_message_for_students(exception_data, test_case):
    """
    Gets called when a test fails because of an exception occuring, rather than
    the test failing because it didn't produce the right output, etc.

    If an exception occurs during the subprocess of the code running, it gets
    returned as a dictionary (since you can't pickle Exception objects and send them
    to a higher process). Otherwise, this function just expects an exception object.
    """

    if isinstance(exception_data, dict):
        # Exception data from the subprocess
        error_type = exception_data['type']
        error_message_str = exception_data['message']
        traceback_list = exception_data['traceback']
        # Attempt to get the last traceback entry for the error location
        if traceback_list:
            error_location = ''.join(traceback_list[-2:]) if len(traceback_list) >= 2 else ''.join(traceback_list)
        else:
            error_location = "No traceback available."
    else:
        # Exception object with traceback
        e = exception_data
        tb_list = traceback.extract_tb(e.__traceback__)
        if tb_list:
            last_traceback = [tb_list[-1]]
            error_location = ''.join(traceback.format_list(last_traceback))
        else:
            error_location = "No traceback available."
        error_type = type(e).__name__
        error_message_str = str(e)

    # Because the student's code is run by exec in a subprocess, it just shows up as <string>
    # These just puts back their python file name in that case, as well as improves
    # some of the messaging to make it easier for students to understand
    # at a glance by clearly separating the location of the error and the error itself.
    error_location = error_location.replace('File "<string>"', f"{default_module_to_test}.py" )
    error_location = error_location.replace(', in <module>', '' )
    error_message = f"\n{error_type}: {error_message_str}"
    error_location = error_location = error_location.replace(error_message, '')

    # Check if 'inputs' is in test_case and set display_inputs_option accordingly
    if test_case.get("inputs", None):
        display_inputs_option = True
    else:
        display_inputs_option = False

    if error_type == "StopIteration":
        pytest.fail(f"{format_error_message(
            custom_message=(f"While trying to run the test, python ran into an error.\n\n"
                            f"LOCATION OF ERROR:\n\n{error_location}\n"
                            f"ERROR MESSAGE:\n{error_message}\n\n"), 
            test_case=test_case,
            display_inputs=display_inputs_option
            )}")
    else:
        # Call pytest.fail with the formatted error message
        pytest.fail(f"{format_error_message(
            custom_message=(f"While trying to run the test, python ran into an error.\n\n"
                            f"LOCATION OF ERROR:\n\n{error_location}\n"
                            f"ERROR MESSAGE:\n{error_message}\n\n"
                            f"HOW TO FIX IT:\n\n"
                            f"If the error occurred in {default_module_to_test}.py or another .py file that you wrote, set a breakpoint at the location in that file where "
                            f"the error occurred and see if you can repeat the error by running your code using the inputs for Test Case {test_case['id_test_case']}. "
                            f"That should help you see what went wrong.\n\n"
                            f"If the error occurred in a different file, reach out to your professor.\n\n"), 
            test_case=test_case,
            display_inputs=display_inputs_option
            )}")

def timeout_message_for_students(test_case):
    """
    Just returns a message for timeout errors.
    I put this in a function just so there is one central place
    to edit the message if I change it in the future.
    """
    test_case_inputs = test_case.get("inputs", "No inputs")
    test_case_inputs = '\n'.join(test_case_inputs)

    return format_error_message(
                custom_message=(f"You got a Timeout Error, meaning this test case didn't complete after {default_timeout_seconds} seconds. "
                                f"The test timed out during test case {test_case["id_test_case"]}. To try and identify the problem, run your code like normal, but enter these EXACT inputs "
                                f"in this order:\n\n"
                                f"{test_case_inputs}\n\n"
                                f"Most likely, "
                                f"you wrote your code in a way that the inputs of this test case make it so your code never exits properly. "
                                f"Double check the test case examples in the instructions and make sure your code isn't asking for additional "
                                f"or fewer inputs than the test case expects.\n\n"),
                test_case=test_case,
                display_inputs=True,
                display_input_prompts=True,
                display_invalid_input_prompts=True)

    
