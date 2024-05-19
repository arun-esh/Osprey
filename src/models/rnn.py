import pickle
import logging
from glob import glob
import re

from src.models.baseline import Baseline
import settings

from torch.optim.lr_scheduler import ReduceLROnPlateau

import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset, SubsetRandomSampler
import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm

from src.utils.commons import force_open, calculate_metrics_extended, padding_collate_sequence_batch

logger = logging.getLogger()


class BaseRnnModule(Baseline, nn.Module):
    
    def __init__(self, hidden_size, num_layers, *args, **kwargs):
        nn.Module.__init__(self)
        Baseline.__init__(self, *args, **kwargs)

        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.snapshot_steps = 2
        self.core = nn.RNN(input_size=self.input_size, hidden_size=self.hidden_size, num_layers=self.num_layers, nonlinearity='tanh',
                          batch_first=True)
        self.hidden2out = nn.Linear(in_features=self.hidden_size, out_features=settings.OUTPUT_LAYER_NODES)

    
    @classmethod
    def short_name(cls) -> str:
        return "base-rnn"

    def forward(self, x):
        out, hn = self.core(x)
        y_hat = self.hidden2out(out[:, -1])
        # y_hat = torch.sigmoid(y_hat)
        return y_hat

    def get_session_path(self, *args):
        return f"{self.session_path}" + self.__class__.short_name() + "/" + "/".join([str(a) for a in args])

    def get_detailed_session_path(self, dataset, *args):
        details = str(dataset) + "-" + str(self)
        return self.get_session_path(details, *args)
    
    def check_stop_early(self, *args, **kwargs):
        return kwargs.get("f2score", 0.0) >= 0.98 and self.early_stop
    
    def reset_modules(self, module, parents_modules_names=[]):
        for name, module in module.named_children():
            if name in settings.ALL_IGNORED_PARAM_RESET:
                continue
            if isinstance(module, nn.ModuleList):
                self.reset_modules(module, parents_modules_names=[*parents_modules_names, name])
            elif isinstance(module, nn.Dropout):
                continue
            else:
                logger.info(f"resetting module parameters: {'.'.join([name, *parents_modules_names])}")
                module.reset_parameters()

    def get_all_folds_checkpoints(self, dataset):
        # main_path = glob(self.get_detailed_session_path(dataset, "weights", f"f{fold}", f"model_f{fold}.pth"))
        main_path = glob(self.get_detailed_session_path(dataset, "weights", "f[0-9]", "model_f[0-9].pth")) # Supports upto 10 folds (from 0 to 9)
        paths = [ pp for pp in main_path if re.search(r"model_f\d{1,2}.pth$", pp)]
        if len(paths) == 0:
            raise RuntimeError("no checkpoint was found. probably the model has not been trained.")
        return paths

    def get_new_optimizer(self, lr, *args, **kwargs):
        return torch.optim.Adam(self.parameters(), lr=lr)
    
    def get_new_scheduler(self, optimizer, *args, **kwargs):
        scheduler_args = {"verbose":False, "min_lr":1e-9, "threshold": 20, "cooldown": 5, "patience": 20, "factor":0.25, "mode": "min"}
        logger.debug(f"scheduler settings: {scheduler_args}")
        return ReduceLROnPlateau(optimizer, **scheduler_args)
    
    def get_dataloaders(self, dataset, test_dataset, train_ids, validation_ids, batch_size):
        train_subsampler = SubsetRandomSampler(train_ids)
        train_loader = DataLoader(dataset, batch_size=batch_size, drop_last=False,
                                                    sampler=train_subsampler, collate_fn=padding_collate_sequence_batch)
        if len(validation_ids) > 0:
            validation_subsampler = SubsetRandomSampler(validation_ids)
            validation_loader = DataLoader(dataset, batch_size=batch_size, drop_last=False,
                                                            sampler=validation_subsampler, collate_fn=padding_collate_sequence_batch)
        elif test_dataset is not None: # initializing test dataset as of validation set
            validation_loader = DataLoader(test_dataset, batch_size=batch_size, drop_last=False, collate_fn=padding_collate_sequence_batch)
        else:
            validation_loader = None
            logger.warning("no validation id nor test dataset is provided")
            # raise ValueError("no validation id nor test dataset is provided")
        return train_loader, validation_loader

    def learn(self, epoch_num:int , batch_size: int, splits: list, train_dataset: Dataset, test_dataset: Dataset=None, weights_checkpoint_path: str=None, condition_save_threshold=0.9):
        if weights_checkpoint_path is not None and len(weights_checkpoint_path):
            checkpoint = torch.load(weights_checkpoint_path)
            self.load_state_dict(checkpoint.get("model", checkpoint))

        logger.info(f"saving epoch condition: f2score>{condition_save_threshold}")
        logger.info("training phase started")
        
        folds_metrics = []
        logger.info(f"number of folds: {len(splits)}")
        for fold, (train_ids, validation_ids) in enumerate(splits):
            self.train()
            logger.info("Resetting Optimizer, Learning rate, and Scheduler")
            self.optimizer = self.get_new_optimizer(self.init_lr)
            self.scheduler = self.get_new_scheduler(self.optimizer)
            last_lr = self.init_lr
            logger.info(f'fetching data for fold #{fold}')
            train_loader, validation_loader = self.get_dataloaders(train_dataset, test_dataset, train_ids, validation_ids, batch_size)
            # Train phase
            total_loss = []
            total_validation_loss = []
            # resetting module parameters
            self.reset_modules(module=self)
            for i in range(epoch_num):
                self.train()
                loss = 0
                epoch_loss = 0
                for (X, y) in tqdm(train_loader, leave=False):
                    self.optimizer.zero_grad()
                    if isinstance(X, tuple) or isinstance(X, list):
                        X = [l.to(self.device) for l in X]
                    else:
                        X = X.to(self.device)
                    y = y.reshape(-1, 1).to(self.device)
                    y_hat = self.forward(X)
                    loss = self.loss_function(y_hat, y)
                    loss.backward()
                    self.optimizer.step()
                    # logger.debug(f"fold: {fold} | epoch: {i} | batch: {batch_index} | loss: {loss}")
                    epoch_loss += loss.item()
                epoch_loss /= len(train_ids)
                total_loss.append(epoch_loss)
                self.scheduler.step(loss)
                if self.optimizer.param_groups[0]["lr"] != last_lr:
                    logger.info(f"fold: {fold} | epoch: {i} | Learning rate changed from: {last_lr} -> {self.optimizer.param_groups[0]['lr']}")
                    last_lr = self.optimizer.param_groups[0]["lr"]

                all_preds = []
                all_targets = []
                validation_loss = 0
                self.eval()
                if validation_loader is None:
                    logger.warning("no validation applied as validation loader is not initialized")
                    continue
                with torch.no_grad():
                    for X, y in tqdm(validation_loader, leave=False):
                        if isinstance(X, tuple) or isinstance(X, list):
                            X = [l.to(self.device) for l in X]
                        else:
                            X = X.to(self.device)
                        y = y.reshape(-1, 1).to(self.device)
                        pred = self.forward(X)
                        loss = self.loss_function(pred, y)
                        validation_loss += loss.item()
                        all_preds.extend(torch.sigmoid(pred) if isinstance(self.loss_function, nn.BCEWithLogitsLoss) else pred)
                        all_targets.extend(y)
                    validation_loss /= len(validation_loader.sampler)
                    total_validation_loss.append(validation_loss)
                all_preds = torch.stack(all_preds)
                all_targets = torch.stack(all_targets)
                
                accuracy_value, recall_value, precision_value, f2score, f05score = calculate_metrics_extended(all_preds, all_targets, device=self.device)
                logger.info(f"fold: {fold} | epoch: {i} | train -> loss: {(epoch_loss):>0.5f} | validation -> loss: {(validation_loss):>0.5f} | accuracy: {(100 * accuracy_value):>0.6f} | precision: {(100 * precision_value):>0.6f} | recall: {(100 * recall_value):>0.6f} | f2: {(100 * f2score):>0.6f} | f0.5: {(100 * f05score):>0.6f}")
                
                epoch_snapshot_path = self.get_detailed_session_path(train_dataset, "weights", f"f{fold}", f"model_f{fold}_e{i}.pth")
                if f2score >= condition_save_threshold:
                    logger.info(f"fold: {fold} | epoch: {i} | saving model at {epoch_snapshot_path}")
                    self.save(epoch_snapshot_path)
                
                if self.check_stop_early(f2score=f2score):
                    logger.info(f"early stop condition satisfied: f2 score => {f2score}")
                    break
            folds_metrics.append((accuracy_value, precision_value, recall_value))
            
            snapshot_path = self.get_detailed_session_path(train_dataset, "weights", f"f{fold}", f"model_f{fold}.pth")
            self.save(snapshot_path)
            plt.clf()
            plt.plot(np.arange(1, 1 + len(total_loss)), np.array(total_loss), "-r", label="training")
            plt.plot(np.arange(1, 1 + len(total_loss)), np.array(total_validation_loss), "-b", label="validation")
            plt.legend()
            plt.title(f"fold #{fold}")
            with force_open(self.get_detailed_session_path(train_dataset, "figures", f"loss_f{fold}.png"), "wb") as f:
                plt.savefig(f, dpi=300)

    def test(self, test_dataset, weights_checkpoint_path):
        for path in weights_checkpoint_path:
            logger.info(f"testing checkpoint at: {path}")
            torch.cuda.empty_cache()
            # self.load_params(weights_checkpoint_path)
            checkpoint = torch.load(path)
            self.load_state_dict(checkpoint.get("model", checkpoint))

            all_preds = []
            all_targets = []
            test_dataloader = DataLoader(test_dataset, batch_size=64, collate_fn=padding_collate_sequence_batch)
            self.eval()
            with torch.no_grad():
                for X, y in test_dataloader:
                    X = X.to(self.device)
                    y = y.to(self.device)
                    y_hat = self.forward(X)
                    y_hat = y_hat.reshape(-1)
                    all_preds.extend(torch.sigmoid(y_hat) if isinstance(self.loss_function, nn.BCEWithLogitsLoss) else y_hat)
                    all_targets.extend(y)

            all_preds = torch.tensor(all_preds)
            all_targets = torch.tensor(all_targets)
            base_path = "/".join(re.split("\\\|/", path)[:-1])
            with force_open(base_path + '/preds.pkl', 'wb') as file:
                pickle.dump(all_preds, file)
                logger.info(f'predictions are saved at: {file.name}')
            with force_open(base_path + '/targets.pkl', 'wb') as file:
                pickle.dump(all_targets, file)
                logger.info(f'targets are saved at: {file.name}')

    def save(self, path):
        with force_open(path, "wb") as f:
            torch.save(self.state_dict(), f)
            logger.info(f"saving sanpshot at {path}")

    def load_params(self, path):
        self.load_state_dict(torch.load(path))
        logger.info(f"loaded model weights from file: {path}")
    
    def __str__(self) -> str:
        return "lr"+ format(self.init_lr, "f") + "-h" + str(self.hidden_size) + "-l" + str(self.num_layers)


class LSTMModule(BaseRnnModule):

    @classmethod
    def short_name(cls) -> str:
        return "lstm"

    def __init__(self, hidden_size, num_layers, *args, **kwargs):
        super().__init__(hidden_size, num_layers, *args, **kwargs)
        self.core = nn.LSTM(input_size=self.input_size, hidden_size=self.hidden_size, num_layers=self.num_layers, batch_first=True)


class GRUModule(BaseRnnModule):

    @classmethod
    def short_name(cls) -> str:
        return "gru"

    def __init__(self, hidden_size, num_layers, *args, **kwargs):
        super().__init__(hidden_size, num_layers, *args, **kwargs)
        self.core = nn.GRU(input_size=self.input_size, hidden_size=self.hidden_size, num_layers=self.num_layers, batch_first=True)

