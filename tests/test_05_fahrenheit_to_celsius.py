max_score = 10  # This value is pulled by yml_generator.py to assign a score to this test.
from conftest import normalize_text, load_student_code, format_error_message, exception_message_for_students
import pytest

# Checks if the input prompts (from using input()) contain the expected prompts.
def test_05_fahrenheit_to_celsius(test_cases):
    try:
        # Ensure test_cases is valid and iterable
        if not isinstance(test_cases, list):
            test_case = {"id_test_case": None}
            exception_message_for_students(ValueError("test_cases should be a list of dictionaries. Contact your professor."), test_case=test_case) 
            return  # Technically not needed, as exception_message_for_students throws a pytest.fail Error, but included for clarity that this ends the test.

        test_case = test_cases[0]
        function_being_tested = 'fahrenheit_to_celsius'
        function_tests = {function_being_tested: [
            # function test cases. Inputs in first position, expected output in second position.
            # If a function takes only a single input, be sure to include a comma after the value so that
            # python recognizes it as a tuple.
            [(32,), 0],
            [(122,), 50],
            [(-13,), -25],
            ]}

        # Grab the necessary data from the test case dictionary
        inputs = test_case["inputs"]

        # Load in the student's code using the updated function
        _, _, _, function_results = load_student_code(inputs, test_case, function_tests=function_tests)

        if function_results.get("FUNCTION ERROR") is not None:
            pytest.fail(f"{format_error_message(
                custom_message=(f"{function_results.get("FUNCTION ERROR")}\n\n"), 
                test_case=test_case,
                )}")
            
        test_results = function_results.get(function_being_tested)

        for index, actual_result in enumerate(test_results):
            test_inputs = function_tests.get(function_being_tested)[index][0]
            test_inputs_str = ', '.join(str(item) for item in test_inputs)
            expected_result = function_tests.get(function_being_tested)[index][1]

            # if the returned value is a string, it will normalize it.
            actual_result = normalize_text(actual_result)
            expected_result = normalize_text(expected_result)

            assert actual_result == expected_result, format_error_message(
                custom_message=(f"When the function: {function_being_tested}\nis provided with the following argument(s):\n\n"
                                f"{test_inputs_str}\n\n"
                                f"the expected return value (ignoring capitalization / punctuation) is:\n\n"
                                f"{expected_result}\n\n"
                                f"However, your function is returning this value (ignoring capitalization / punctuation):\n\n"
                                f"{actual_result}\n\n"
                                f"Make sure your function is returning a value and that the logic matches "
                                f"what the instructions say."),
                test_case=test_case,
            ) 

    # assert raises an AssertionError, but I don't want to actually catch it
    # this is just so I can have another Exception catch below it in case
    # anything else goes wrong.
    except AssertionError:
        raise
    
    except Exception as e:
        # Handle other exceptions
        exception_message_for_students(e, test_case)