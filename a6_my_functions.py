# Name: Ethan Housley
# You will place most of your functions for this assignment in this file.

# this is the sum of 2 numbers, which is called in function smorgasbord
def sum_two_numbers(num1, num2):
    return num1 + num2

# is even function
def is_even(int):
    return int % 2 == 0

# this function will tell you if a int is even or odd
def get_number_parity(int):
    if is_even(int):
        return f'{int} is even'
    else:
        return f'{int} is odd'

def fahrenheit_to_celsius(temp):
    celsius = (temp - 32) * (5/9)
    return celsius

def min_max_mean(lst):
    min = lst[0]
    max = lst[0]
    mean = 0
    for i in lst:
        # this will go thru and change the min to the new lowest num
        if min > i:
            min = i
        # this will go thru and change the min to the new lowest num
        if max < i:
            max = i
        mean += i
    mean = mean / len(lst)
    return [min, max, mean]

def dog_message(name, age=0):
    return f"I am a dog named {name} and I'm {age} years old!"

def classify_age(age, senior_age=65):
    if age < 18:
        return 'Minor'
    elif age < senior_age:
        return 'Adult'
    else:
        return 'Senior'

def calculate_total(price, quantity, discount_percent, threshold_total=100, bonus_discount=float(0.02)):
    subtotal = float(price) * float(quantity)
    if subtotal <= threshold_total:
        total = subtotal - subtotal * float(discount_percent)
    # this elif statement isn't necessary but i realized it after the fact
    elif subtotal > threshold_total:
        # honestly not sure if I need to make sure discount percent and bonus discount are floats, did it anyway
        total = subtotal - subtotal * (float(discount_percent) + float(bonus_discount))
    return total
