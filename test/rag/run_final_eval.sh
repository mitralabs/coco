# # fill db
# WAND_MODE=offline python main.py data.custom_split=full data.clear_db=true data.fill_db.skip=false retrieval.skip=true generation.skip=true

# # run final evals on train
# python main.py wandb.name=final-train-llama-rag generation=rag generation.use_oai_coco_client=false 'generation.llm_model=["meta-llama/Llama-3.3-70B-Instruct", "openai"]' data.custom_split=train
python main.py wandb.name=final-train-llama-agent generation=agent generation.use_oai_coco_client=false 'generation.llm_model=["meta-llama/Llama-3.3-70B-Instruct", "openai"]' data.custom_split=train
# python main.py wandb.name=final-train-4o-rag generation=rag generation.use_oai_coco_client=true 'generation.llm_model=["gpt-4o-2024-11-20", "openai"]' data.custom_split=train
python main.py wandb.name=final-train-4o-agent generation=agent generation.use_oai_coco_client=true 'generation.llm_model=["gpt-4o-2024-11-20", "openai"]' data.custom_split=train

# # run final evals on test
# python main.py wandb.name=final-test-llama-rag generation=rag generation.use_oai_coco_client=false 'generation.llm_model=["meta-llama/Llama-3.3-70B-Instruct", "openai"]' data.custom_split=test
python main.py wandb.name=final-test-llama-agent generation=agent generation.use_oai_coco_client=false 'generation.llm_model=["meta-llama/Llama-3.3-70B-Instruct", "openai"]' data.custom_split=test
# python main.py wandb.name=final-test-4o-rag generation=rag generation.use_oai_coco_client=true 'generation.llm_model=["gpt-4o-2024-11-20", "openai"]' data.custom_split=test
python main.py wandb.name=final-test-4o-agent generation=agent generation.use_oai_coco_client=true 'generation.llm_model=["gpt-4o-2024-11-20", "openai"]' data.custom_split=test

# # run final evals on full
# python main.py wandb.name=final-full-llama-rag generation=rag generation.use_oai_coco_client=false 'generation.llm_model=["meta-llama/Llama-3.3-70B-Instruct", "openai"]' data.custom_split=full
python main.py wandb.name=final-full-llama-agent generation=agent generation.use_oai_coco_client=false 'generation.llm_model=["meta-llama/Llama-3.3-70B-Instruct", "openai"]' data.custom_split=full
# python main.py wandb.name=final-full-4o-rag generation=rag generation.use_oai_coco_client=true 'generation.llm_model=["gpt-4o-2024-11-20", "openai"]' data.custom_split=full
python main.py wandb.name=final-full-4o-agent generation=agent generation.use_oai_coco_client=true 'generation.llm_model=["gpt-4o-2024-11-20", "openai"]' data.custom_split=full
