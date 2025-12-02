import sys
import os

# Add src_v2 to path
sys.path.append(os.getcwd())

from src_v2.tools.math_tools import CalculatorTool

tool = CalculatorTool()

print("--- Test 1: Expression ---")
print(tool.run("2 * degrees(atan(36 / (2 * 28)))"))

print("\n--- Test 2: Natural Language (Simulating bad LLM call) ---")
print(tool.run("calculate the horizontal FOV of a 28mm lens on a 36mm sensor"))
