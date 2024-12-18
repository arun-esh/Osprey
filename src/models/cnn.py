import torch

from src.models import AbstractFeedForward
from settings import settings


class EbrahimiCNN(AbstractFeedForward):

    def __init__(self, *args, **kwargs):
        super(AbstractFeedForward, self).__init__(*args, **kwargs)
        
        self.cnn = torch.nn.Conv1d(self.input_size, 2000, 1, groups=1)
        self.out = torch.nn.Linear(2000, settings.OUTPUT_LAYER_NODES)

    def forward(self, x):
        if x.is_sparse:
            x = x.to_dense()
        x = self.activation(self.cnn(x))
        x = torch.squeeze(x)
        x = self.out(x)
        x = torch.sigmoid(x)

        return x
    
    @classmethod
    def short_name(cls) -> str:
        return "ebrahimi-cnn"

    def __str__(self) -> str:
        return str(self.init_lr) + "-" + "2000.1"
