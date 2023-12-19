import numpy as np
import torch
from tqdm import tqdm

from deepcp.regression.utils.metrics import Metrics


class SplitPredictor(object):
    def __init__(self, model, device):
        self._model = model
        self._device = device
        self._metric = Metrics()

    def calibrate(self, cal_dataloader, alpha):
        predicts_list = []
        labels_list = []
        x_list = []
        with torch.no_grad():
            for examples in cal_dataloader:
                tmp_x, tmp_labels = examples[0].to(self._device), examples[1]
                tmp_predicts = self._model(tmp_x).detach().cpu()
                x_list.append(tmp_x)
                predicts_list.append(tmp_predicts)
                labels_list.append(tmp_labels)
            predicts = torch.cat(predicts_list).float()
            labels = torch.cat(labels_list)
            x = torch.cat(x_list).float()
        self.predicts = predicts
        self.labels = labels
        self.x = x
        self.calculate_threshold(predicts, labels, alpha)

    def calculate_threshold(self, predicts, y_truth, alpha):
        self.scores = torch.abs(predicts - y_truth)

        self.q_hat = torch.quantile(self.scores,
                                    np.ceil((self.scores.shape[0] + 1) * (1 - alpha)) / self.scores.shape[0])

    def predict(self, x_batch):
        predicts_batch = self._model(x_batch.to(self._device)).float()
        lower_bound = predicts_batch - self.q_hat
        upper_bound = predicts_batch + self.q_hat
        prediction_intervals = torch.stack([lower_bound, upper_bound], dim=1)
        return prediction_intervals

    def evaluate(self, data_loader):
        y_list = []
        x_list = []
        predict_list = []
        with torch.no_grad():
            for examples in data_loader:
                tmp_x, tmp_y = examples[0].to(self._device), examples[1]
                tmp_prediction_intervals = self.predict(tmp_x)
                y_list.append(tmp_y)
                x_list.append(tmp_x)
                predict_list.append(tmp_prediction_intervals)

        predicts = torch.cat(predict_list).float().cpu()
        test_y = torch.cat(y_list)
        x = torch.cat(x_list).float()

        res_dict = {}
        res_dict["Coverage_rate"] = self._metric('coverage_rate')(predicts, test_y)
        res_dict["Average_size"] = self._metric('average_size')(predicts, test_y)
        return res_dict
