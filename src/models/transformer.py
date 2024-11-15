from torch.utils.data import DataLoader, SubsetRandomSampler
from transformers import AutoConfig, AutoModelForSequenceClassification

from src.models import AbstractFeedForward
from settings import OUTPUT_LAYER_NODES

import logging

logger = logging.getLogger()


class DistilrobertaFinetuningClassifier(AbstractFeedForward):

    def __init__(self, dropout=0.0, *args, **kwargs):
        super(AbstractFeedForward, self).__init__(*args, dimension_list=[], dropout_list=[], **kwargs)
        config = AutoConfig.from_pretrained('distilroberta-base')
        config.hidden_dropout_prob = dropout
        config.num_labels = OUTPUT_LAYER_NODES
        self.core = AutoModelForSequenceClassification.from_pretrained("distilroberta-base", config=config)

    def forward(self, x):
        x = self.core(input_ids=x[0], attention_mask=x[1])

        return x[0]
    
    @classmethod
    def short_name(cls) -> str:
        return "distilroberta-classifier"
    
    def get_dataloaders(self, dataset, train_ids, validation_ids, batch_size):
        train_subsampler = SubsetRandomSampler(train_ids)
        validation_subsampler = SubsetRandomSampler(validation_ids)
        train_loader = DataLoader(dataset, batch_size=batch_size,
                                                    sampler=train_subsampler, num_workers=3)
        validation_loader = DataLoader(dataset, batch_size=(256 if len(validation_ids) > 1024 else len(validation_ids)),
                                       sampler=validation_subsampler, num_workers=1)
        
        return train_loader, validation_loader
