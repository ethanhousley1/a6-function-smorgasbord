# Name: Ethan Housley
# Enter your python code below. Replace this line with a description.
# lots of functions will be called to this file. we must import them
from a6_my_functions import *


# this is the welcome message

def welcome_message(name):
    print(f'Hello {name}, welcome to IS 303!')

welcome_message('Diego')
welcome_message('Mai')


print(sum_two_numbers(5,7))
print(sum_two_numbers(10000.5, -30))

print(is_even(7))
print(is_even(120))

print(get_number_parity(5))
print(get_number_parity(10))

print(fahrenheit_to_celsius(32))
print(fahrenheit_to_celsius(75))

numbers_list_1 = [20, 45, 23, 2, 87, 3]
print(min_max_mean(numbers_list_1))

print(dog_message('Spot', 7))
print(dog_message('Peppy'))

print(classify_age(60, 55))
print(classify_age(62))

for i in range(2):
    price = input('Enter the price for the product purchased: ')
    quantity = input('Enter the quantity of the product purchased: ')
    discount_percent = input('Enter the discount percent (formatted as a decimal): ')
    total = calculate_total(price, quantity, discount_percent)
    print(f"The total price after discounts is: ${total}")