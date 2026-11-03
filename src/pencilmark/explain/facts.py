"""Rule facts: the one-sentence reasons solvers give for a rule, used as the `why` of explanation sub-steps. Chosen
from the facts Cracking the Cryptic hosts repeat most (docs/research/rule_facts_library.md in the research notes;
each in at least 5 solve videos), in our own words."""

RULE_FACTS = {
    "thermo": "Digits on a thermometer increase from the bulb to the tip, so a cell with k cells before it is at least k + 1.",
    "slow_thermo": "Digits on a slow thermometer never decrease from the bulb to the tip.",
    "whisper": "Neighbours on a German whisper differ by at least 5, so 5 can never be on the line.",
    "dutch_whisper": "Neighbours on a Dutch whisper differ by at least 4.",
    "renban": "A renban line holds a set of consecutive digits, in any order, with no repeats.",
    "palindrome": "A palindrome line reads the same from both ends, so mirrored cells hold the same digit.",
    "entropic": "Any three neighbouring cells on an entropic line hold one low (1-3), one middle (4-6) and one high (7-9) digit.",
    "modular": "Any three neighbouring cells on a modular line hold digits with different remainders when divided by 3.",
    "kropki_chain": "A white dot joins two consecutive digits; a black dot joins a digit and its double, so 5, 7 and 9 never "
    "sit on a black dot.",
    "region_sum": "A region-sum line has the same total in every box it passes through.",
    "parity": "Neighbours on a parity line alternate between odd and even.",
    "between": "Digits on a between line lie strictly between the two circle digits at its ends.",
    "zipper": "Cells the same distance from the middle of a zipper line add up to the same total; on a line with a "
    "centre cell that total is the centre digit, so the centre is the line's largest digit.",
    "cage": "Digits in a cage don't repeat and add up to its total.",
    "arrow": "The digits on an arrow add up to the digit in its circle.",
}
