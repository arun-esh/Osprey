import logging

import torch
from torch.utils.data import DataLoader
from transformers import BertForSequenceClassification
from transformers import get_linear_schedule_with_warmup

from src.main import initiate_datasets
import settings

logger = logging.getLogger()

def finetune_tranformer_per_message(device="cpu", dataset_name="raw-v2-dataset-toy", model_output_path=None):
    torch.cuda.empty_cache()

    init_lr = 2e-5
    num_epochs = 6
    batch_size = 16
    logger.info("initializing the dataset")
    datasets = initiate_datasets(settings.datasets, device=device)
    train_set = datasets[dataset_name][0]
    train_set.prepare()
    train_set.to(device)
    train_dataloader = DataLoader(train_set, batch_size)
    logger.info("loading pretrained bert model")
    model = BertForSequenceClassification.from_pretrained(
        "bert-base-uncased", num_labels = 1, output_attentions = False, output_hidden_states = False)
    
    if device == "cuda":
        logger.info("switching model to cuda")
        model.cuda()
    
    optimizer = torch.optim.AdamW(model.parameters(), lr=init_lr, eps=1e-8)
    num_training_steps = num_epochs * len(train_dataloader)
    scheduler = get_linear_schedule_with_warmup(optimizer=optimizer, num_warmup_steps=0, num_training_steps=num_training_steps)

    logger.info("fine-tuning started")
    model.train()
    for epoch in range(num_epochs):
        epoch_loss = 0
        for batch_attention_mask, batch_input_ids, batch_label in train_dataloader:
            model.zero_grad()
            
            loss, logits = model(batch_input_ids, attention_mask=batch_attention_mask, labels=batch_label, token_type_ids=None, return_dict=False)
            epoch_loss += (loss * len(batch_input_ids))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
        epoch_loss = epoch_loss / len(train_dataloader)
        logger.info(f"epoch: #{epoch} | loss: {epoch_loss}")
    if model_output_path:
        model_output_path = model_output_path if model_output_path[-1] in ("\\", "/") else model_output_path + "/"
    else:
        model_output_path = train_set.get_session_path("")
    logger.info(f"saving the transformer and tokenizer at: {model_output_path}")
    model_to_save = model.module if hasattr(model, 'module') else model
    model_to_save.save_pretrained(model_output_path)
    train_set.tokenizer.save_pretrained(model_output_path)
