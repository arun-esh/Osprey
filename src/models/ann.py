import pickle
import logging

import torchmetrics
from torch.optim.lr_scheduler import ExponentialLR

from src.models.baseline import Baseline
from src.utils.commons import force_open
from settings import settings

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

import matplotlib.pyplot as plt
import numpy as np

from sklearn.model_selection import KFold

logger = logging.getLogger()


class ANNModule(Baseline, torch.nn.Module):

    def __init__(self, dimension_list, activation, loss_func, lr, input_size, module_session_path,
                 device='cpu', **kwargs):
        Baseline.__init__(self, input_size=input_size)
        torch.nn.Module.__init__(self)
        
        self.init_lr = lr
        self.dimension_list = dimension_list

        
        self.i2h = nn.Linear(input_size,
                             dimension_list[0] if len(dimension_list) > 0 else 2)
        self.layers = nn.ModuleList()
        for i, j in zip(dimension_list, dimension_list[1:]):
            self.layers.append(nn.Linear(in_features=i, out_features=j))
        self.h2o = torch.nn.Linear(dimension_list[-1] if len(dimension_list) > 0 else input_size, 2)
        self.activation = activation
        self.optimizer = torch.optim.SGD(self.parameters(), lr=lr, momentum=0.9)
        self.scheduler = ExponentialLR(self.optimizer, gamma=0.9, verbose=True)

        self.loss_function = loss_func

        self.session_path = module_session_path if module_session_path[-1] == "\\" or module_session_path[
            -1] == "/" else module_session_path + "/"

        self.snapshot_steps = 2
        self.device = device

    @classmethod
    def short_name(cls) -> str:
        return "ann"

    def forward(self, x):
        """

        Args:
            x: Tensor object

        Returns: prediction of the model

        """
        x = self.activation(self.i2h(x))
        for layer in self.layers:
            x = self.activation(layer(x))

        x = self.h2o(x)
        x = torch.softmax(x, dim=1)
        # x = torch.sigmoid(x)
        return x

    def get_session_path(self, *args):
        return f"{self.session_path}" + "ann/" + "/".join([str(a) for a in args])
    
    def get_detailed_session_path(self, dataset, *args):
        details = str(dataset) + "-" + str(self)
        return self.get_session_path(details, *args)
    
    def reset_modules(self, module, parents_modules_names=[]):
        for name, module in module.named_children():
            if name in settings.IGNORED_PARAM_RESET:
                continue
            if isinstance(module, nn.ModuleList):
                self.reset_modules(module, parents_modules_names=[*parents_modules_names, name])
            else:
                logger.info(f"resetting module parameters {'.'.join([name, *parents_modules_names])}")
                module.reset_parameters()

    def learn(self, epoch_num: int, batch_size: int, k_fold: int, train_dataset: Dataset):

        train_dataset.to(self.device)
        accuracy = torchmetrics.Accuracy('multiclass', num_classes=2, top_k=1).to(self.device)
        precision = torchmetrics.Precision('multiclass', num_classes=2, top_k=1).to(self.device)
        recall = torchmetrics.Recall('multiclass', num_classes=2, top_k=1).to(self.device)
        logger.info("training phase started")
        kfold = KFold(n_splits=k_fold)
        for fold, (train_ids, validation_ids) in enumerate(kfold.split(train_dataset)):
            logger.info(f'getting data for fold #{fold}')
            train_subsampler = torch.utils.data.SubsetRandomSampler(train_ids)
            validation_subsampler = torch.utils.data.SubsetRandomSampler(validation_ids)
            train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=batch_size,
                                                       sampler=train_subsampler)
            validation_loader = torch.utils.data.DataLoader(train_dataset, batch_size=batch_size,
                                                            sampler=validation_subsampler)
            # Train phase
            total_loss = []
            # resetting module parameters
            self.reset_modules(module=self)
            for i in range(epoch_num):
                loss = 0
                for batch_index, (X, y) in enumerate(train_loader):
                    # y = y.type(torch.float)
                    y_hat = self.forward(X)
                    self.optimizer.zero_grad()
                    loss = self.loss_function(y_hat, y)
                    loss.backward()
                    self.optimizer.step()
                    logger.info(f"fold: {fold} | epoch: {i} | batch: {batch_index} | loss: {loss}")
                    total_loss.append(loss.item())
                self.scheduler.step()
            # Validation phase
            all_preds = []
            all_targets = []
            size = len(validation_loader)
            num_batches = len(validation_loader)
            test_loss, correct = 0, 0
            with torch.no_grad():
                for batch_index, (X, y) in enumerate(validation_loader):
                    # y = y.type(torch.float)
                    pred = self.forward(X)
                    all_preds.extend(pred)
                    # all_preds.extend(pred.argmax(1))
                    all_targets.extend(y)
                    # test_loss += self.loss_function(pred, y).item()
                    # correct += (pred.argmax(1) == y).type(torch.float).sum().item()
            # test_loss /= num_batches
            # correct /= size
            all_preds = torch.stack(all_preds)
            all_targets = torch.stack(all_targets)
            # logger.info(f"Validation Error: Avg loss: {test_loss:>8f}")
            logger.info(f'torchmetrics Accuracy: {(100 * accuracy(all_preds, all_targets)):>0.1f}')
            logger.info(f'torchmetrics precision: {(100 * precision(all_preds, all_targets)):>0.1f}')
            logger.info(f'torchmetrics Recall: {(100 * recall(all_preds, all_targets)):>0.1f}')

            snapshot_path = self.get_detailed_session_path(train_dataset, "weights", f"f{fold}", f"model_fold{fold}.pth")
            self.save(snapshot_path)
            plt.clf()
            plt.plot(np.array(total_loss))
            with force_open(self.get_detailed_session_path(train_dataset, "figures", f"f{fold}", f"model_fold{fold}_loss.png"), "wb") as f:
                plt.savefig(f)
            # plt.show()

    def test(self, test_dataset):
        all_preds = []
        all_targets = []
        test_dataset.to(self.device)
        test_dataloader = DataLoader(test_dataset, batch_size=64)
        with torch.no_grad():
            for X, y in test_dataloader:
                # y = y.type(torch.float)
                pred = self.forward(X)
                all_preds.extend(pred)
                all_targets.extend(y)

        all_preds = torch.stack(all_preds)
        all_targets = torch.stack(all_targets)
        with force_open(self.get_detailed_session_path(test_dataset, 'preds.pkl'), 'wb') as file:
            pickle.dump(all_preds, file)
            logger.info('predictions are saved.')
        with force_open(self.get_detailed_session_path(test_dataset, 'targets.pkl'), 'wb') as file:
            pickle.dump(all_targets, file)
            logger.info('targets are saved.')

    def eval(self, path):
        Baseline.eval(self, path, device=self.device)

    def save(self, path):
        with force_open(path, "wb") as f:
            torch.save(self.state_dict(), f)
            logger.info(f"saving model at {path}")

    def load_params(self, path):
        try:
            self.load_state_dict(torch.load(path))
            logger.info("parameters loaded successfully")
        except Exception as e:
            logger.debug(e)

    def __str__(self) -> str:
        return str(self.init_lr) + "-" +".".join((str(l) for l in self.dimension_list))
    