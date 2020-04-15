#!/usr/bin/env python3

# Copyright 2020 The Johns Hopkins University (author: Jiatong Shi)


import torch
import numpy as np
import copy
import time
import librosa
from scipy import signal

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def create_src_key_padding_mask(src_len, max_len):
    bs = len(src_len)
    mask = np.zeros((bs, max_len))
    for i in range(bs):
        mask[i, :src_len[i]] = 1
    return torch.from_numpy(mask).float()


def train_one_epoch(train_loader, model, device, optimizer, criterion, args):
    losses = AverageMeter()
    model.train()
    start = time.time()
    for step, (phone, mean_list, duration, length) in enumerate(train_loader, 1):
        phone = phone.to(device)
        mean_list = mean_list.to(device).float()
        duration = duration.to(device)
        length = length.to(device).long()
        length_mask = create_src_key_padding_mask(length, args.max_len)
        length_mask = length_mask.to(device)
        length = length.to(device)

        output = model(phone, mean_list, src_key_padding_mask=length)

        train_loss = criterion(output, duration, length_mask)

        optimizer.zero_grad()
        train_loss.backward()
        if args.gradclip > 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.gradclip)
        optimizer.step_and_update_lr()
        losses.update(train_loss.item(), phone.size(0))
        if step % 10000 == 0:
            end = time.time()
            print("step {}: train_loss {} -- sum_time: {}s".format(step, losses.avg, end - start))

    info = {'loss': losses.avg}
    return info


def validate(dev_loader, model, device, criterion, args):
    losses = AverageMeter()
    model.eval()

    with torch.no_grad():
        for step, (phone, mean_list, duration, length) in enumerate(dev_loader, 1):
            phone = phone.to(device)
            mean_list = mean_list.to(device).float()
            duration = duration.to(device)
            length = length.to(device).long()
            length_mask = create_src_key_padding_mask(length, args.max_len)
            length_mask = length_mask.to(device)
            length = length.to(device)

            output = model(phone, mean_list, src_key_padding_mask=length)
            val_loss = criterion(output, duration, length_mask)
            losses.update(val_loss.item(), phone.size(0))
            if step % 1000 == 0:
                print("step {}: {}".format(step, losses.avg))

    info = {'loss': losses.avg}
    return info


class AverageMeter(object):
    """Computes and stores the average and current value"""
    def __init__(self):
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count


def save_checkpoint(state, model_filename):
    torch.save(state, model_filename)
    return 0


def record_info(train_info, dev_info, epoch, logger):
    loss_info = {
        "train_loss": train_info['loss'],
        "dev_loss": dev_info['loss']}
    logger.add_scalars("losses", loss_info, epoch)
    return 0


