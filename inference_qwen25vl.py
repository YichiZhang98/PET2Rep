from transformers import Qwen2_5_VLForConditionalGeneration, AutoTokenizer, AutoProcessor, GenerationConfig
from qwen_vl_utils import process_vision_info
import torch

import os
import json

from PIL import Image


with open(os.path.join('prompts','general_prompt_v2.jsonl'), 'r', encoding='utf-8')  as f:
    default_prompt = [json.loads(line) for line in f if line.strip()]
    
model_path = 'Qwen/Qwen2.5-VL-32B-Instruct'


model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
    model_path,
    torch_dtype=torch.bfloat16,
    # attn_implementation="flash_attention_2",
    attn_implementation="sdpa",
    device_map="auto",
)
processor = AutoProcessor.from_pretrained(model_path)


generation_config = GenerationConfig(
    temperature=0.7,       
    max_new_tokens=1024,    
    top_p=1,             
    top_k=50,              
    do_sample=True,       
    repetition_penalty=1
)


output_list = []
for subject_prompt in default_prompt:
    subject_id = subject_prompt['patient_id']
    prompt_system = subject_prompt['prompt_system']
    prompt_user_text = subject_prompt['prompt_user_text']
    image_paths = subject_prompt['prompt_image_fuse']
    images = [Image.open(path) for path in image_paths]
    ground_truth = subject_prompt['answer']
    messages = [
        {
            "role":"system",
            "content":subject_prompt["prompt_system"]
        },

        {
            "role":"user",
            "content":[
                *[{"type": "image", "image": img} for img in images],
                {"type":"text","text":subject_prompt['prompt_user_text']}
                ]
                }
    ]
    
    text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    )
    inputs = inputs.to("cuda")
    
    generated_ids = model.generate(**inputs, generation_config=generation_config)
    generated_ids_trimmed = [
        out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    output_text = processor.batch_decode(
        generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )
    

    output_unit = {
        "subject_id": subject_id, 
        "llm_output": output_text,
        "ground_truth": ground_truth
    }
    output_list.append(output_unit)


with open(os.path.join('origin_results','result_qwen25vl-32b_v2_git.jsonl'), 'w', encoding='utf-8') as f:
    for item in output_list:

        f.write(json.dumps(item, ensure_ascii=False) + '\n')

