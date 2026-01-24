
import numpy as np
import pytest
from tensorguard.core.adapters import MoEAdapter

def test_iosp_gating_logic():
    adapter = MoEAdapter()
    
    # Test Case 1: Visual Primary (geometric, shapes, objects, obstacles)
    weights_visual = adapter.get_expert_gate_weights("Identify geometric shapes and obstacles")
    assert weights_visual["visual_primary"] > weights_visual["manipulation_grasp"]
    assert weights_visual["visual_primary"] > weights_visual["language_semantic"]
    
    # Test Case 2: Manipulation Grasp (force, torque, contact, friction, gripper)
    weights_grasp = adapter.get_expert_gate_weights("Apply high force with the gripper")
    assert weights_grasp["manipulation_grasp"] > weights_grasp["visual_primary"]
    assert weights_grasp["manipulation_grasp"] > weights_grasp["visual_aux"]
    
    # Test Case 3: Language Semantic (verbs, instructions, goal, intent, command)
    weights_lang = adapter.get_expert_gate_weights("Follow the command and verbal instructions")
    assert weights_lang["language_semantic"] > weights_lang["visual_primary"]
    assert weights_lang["language_semantic"] > weights_lang["manipulation_grasp"]
    
    # Test Case 4: Visual Aux (color, texture, depth, lighting, shadows)
    weights_aux = adapter.get_expert_gate_weights("Analyze the lighting and color texture")
    assert weights_aux["visual_aux"] > weights_aux["visual_primary"]
    
    # Test Case 5: Empty instruction (should be uniform)
    weights_empty = adapter.get_expert_gate_weights("")
    # All weights should be close to 0.25 (1/4)
    for exp in adapter.experts:
        assert pytest.approx(weights_empty[exp], 0.01) == 0.25

    print("\nIOSP Gating Weight Distribution Examples:")
    instr_list = [
        "Pick up the red cube with firm gripper contact",
        "Move towards the geometric obstacle",
        "Wait for the next verbal command"
    ]
    for instr in instr_list:
        w = adapter.get_expert_gate_weights(instr)
        top_expert = max(w, key=w.get)
        print(f"Instruction: '{instr}' -> Top Expert: {top_expert} ({w[top_expert]:.2%})")

if __name__ == "__main__":
    test_iosp_gating_logic()
