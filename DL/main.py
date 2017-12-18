from __future__ import print_function, division
import os
import argparse
import numpy as np
import torch
import torch.nn as nn
from torch.autograd import Variable
from model import SA_NET
from test import test
from evaluate import evaluate
from torch.optim import Adam
import time
import random
from constants import *
from utils import setup_logger

parser = argparse.ArgumentParser(description='Sentiment-Analysis')
parser.add_argument(
    '--train',
    default = False,
    metavar = 'T',
    help = 'train model (set False to evaluate)')
parser.add_argument(
    '--gpu',
    default=True,
    metavar='G',
    help='using GPU')
parser.add_argument(
    '--model-load',
    default=True,
    metavar='L',
    help='load trained model')
parser.add_argument(
    '--lr',
    type=float,
    default=0.001,
    metavar='LR',
    help='learning rate')
parser.add_argument(
    '--seed',
    type=int,
    default=233,
    metavar='S',
    help='random seed')
parser.add_argument(
    '--workers',
    type=int,
    default=4,
    metavar='W',
    help='how many training processes to use')
parser.add_argument(
    '--tag',
    type=str,
    default='CN',
    metavar='TG',
    help='language of corpus')
parser.add_argument(
    '--model-dir',
    type=str,
    default='trained_models/',
    metavar='MD',
    help='directory to store trained models')
parser.add_argument(
    '--log-dir',
    type=str,
    default='logs/',
    metavar='LD',
    help='directory to store logs')
parser.add_argument(
    '--epoch',
    type=int,
    default=0,
    metavar='EP',
    help='current epoch, used to pass parameters, do not change')
parser.add_argument(
    '--gamma',
    type=float,
    default=0.96,
    metavar='GM',
    help='to reduce learning rate gradually in simulated annealing')

if __name__ == '__main__':
    args = parser.parse_args()
    torch.set_default_tensor_type('torch.DoubleTensor')
    #mp.set_start_method('spawn')
    torch.manual_seed(args.seed)
    random.seed(args.seed)
    if not os.path.exists(args.model_dir):
        os.mkdir(args.model_dir)
    if not os.path.exists(args.log_dir):
        os.mkdir(args.log_dir)
    if args.epoch == 0 and args.train:
        for log in os.listdir(args.log_dir):
            os.remove(os.path.join(args.log_dir, log))
    
    if args.train:
        shared_model = SA_NET(Embedding_Dim[Tag_Dict[args.tag]])
        if args.model_load:
            try:
                saved_state = torch.load(os.path.join(args.model_dir, 'best_model.dat'))
                shared_model.load_state_dict(saved_state)
            except:
                print('Cannot load existing model from file!')
        if args.gpu:
            shared_model = shared_model.cuda()

        optimizer = Adam(shared_model.parameters(), lr=args.lr)
        criterion = nn.CrossEntropyLoss()
        dataset = np.load(os.path.join(Dataset_Dir, Tag_Name[Tag_Dict[args.tag]], "%s_train.npz" % Tag_Name[Tag_Dict[args.tag]]))
        targets = dataset["arr_0"]
        max_accuracy = 0.0

        while True:
            args.epoch += 1
            print('=====> Train at epoch %d, Learning rate %0.6f <=====' % (args.epoch, args.lr))
            start_time = time.time()
            log = setup_logger(0, 'epoch%d' % args.epoch, os.path.join(args.log_dir, 'epoch%d_log.txt' % args.epoch))
            log.info('Train time ' + time.strftime("%Hh %Mm %Ss", time.gmtime(time.time() - start_time)) + ', ' + 'Training started.')
            
            order = list(range(targets.shape[0]))
            random.shuffle(order)
            losses = 0
            correct_cnt = 0

            for i in range(targets.shape[0]):
                idx = order[i]
                if dataset["arr_%d" % (idx + 1)].shape[0] == 0:
                    continue

                data = Variable(torch.from_numpy(dataset["arr_%d" % (idx + 1)]))
                target = Variable(torch.DoubleTensor([int(targets[idx])]), requires_grad = False)
                if args.gpu:
                    data = data.cuda()
                    target = target.cuda()

                output = shared_model(data).squeeze(0)
                if (output.data.cpu().numpy()[0] < 0.5 and targets[idx] == 0) or (output.data.cpu().numpy()[0] >= 0.5 and targets[idx] == 1):
                    correct_cnt += 1
                #output = F.log_softmax(output)

                optimizer.zero_grad()
                loss = criterion(output, target)
                loss.backward()
                if args.gpu:
                    loss = loss.cpu()

                optimizer.step()
                losses += loss
                if (i + 1) % 100 == 0:
                    print(output)
                    log.info('accuracy: %d%%' % correct_cnt)
                    correct_cnt = 0
                    log.info('Train time ' + time.strftime("%Hh %Mm %Ss", time.gmtime(time.time() - start_time)) + ', ' + 'Mean loss: %0.4f' % (loss.data.numpy()[0] % 100))

            state_to_save = shared_model.state_dict()
            torch.save(state_to_save, os.path.join(args.model_dir, 'epoch%d.dat' % args.epoch))
            accuracy = test(args, shared_model, os.path.join(Dataset_Dir, Tag_Name[Tag_Dict[args.tag]], "%s_test.npz" % Tag_Name[Tag_Dict[args.tag]]))
            print('Overall accuracy = %0.2f%%' % (100 * accuracy))
            if accuracy > max_accuracy:
                max_accuracy = accuracy
                torch.save(state_to_save, os.path.join(args.model_dir, 'best_model.dat'))

            args.lr *= args.gamma
            for param_group in optimizer.param_groups:
                param_group['lr'] = args.lr
    else:
        evaluate(args, os.path.join(Dataset_Dir, 'task2input.xml'), os.path.join(Dataset_Dir, 'task2output.xml'))