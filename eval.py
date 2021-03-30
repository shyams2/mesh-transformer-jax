import argparse
import json
import time

import numpy as np
import wandb
from tqdm import tqdm

from tasks.lambada import LambadaTask
from tasks.winogrande import WinograndeTask

from mesh_transformer.build_model import build_model
from tfrecord_loader import TFRecordNewInputs


def parse_args():
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--tpu", type=str, help="Name of TPU to train on.")
    parser.add_argument("--tpu_region", type=str, help="Region of TPU to train on.")
    parser.add_argument("--preemptible", action="store_true")

    parser.add_argument("--config", type=str, default=None, help="Config file location")

    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_args()
    params = json.load(open(args.config))

    tpu_name = args.tpu
    region = args.tpu_region
    preemptible = args.preemptible

    gradient_accumulation_steps = params.get("gradient_accumulation_steps", 1)
    per_replica_batch = params["per_replica_batch"]
    tpu_size = params["tpu_size"]
    cores_per_replica = params["cores_per_replica"]

    bucket = params["bucket"]
    model_dir = params["model_dir"]
    layers = params["layers"]
    d_model = params["d_model"]
    n_heads = params["n_heads"]
    n_vocab = params["n_vocab"]
    seq = params["seq"]
    norm = params["norm"]

    total_batch = per_replica_batch * tpu_size // cores_per_replica

    val_dataset = TFRecordNewInputs(f"data/{params['val_set']}",
                                    batch_size=(total_batch,),
                                    sample_size=seq)

    lambada = LambadaTask(seq)
    winogrande = WinograndeTask(seq)

    t = build_model(params, tpu_name, region, preemptible)

    step, aux = t.load(bucket, model_dir)
    t.move()

    print(lambada.run(total_batch, t))
    print(winogrande.run(total_batch, t))

    val_loss = []
    for i in tqdm(val_dataset.sample_once(), desc=f"validation set"):
        val_loss.append(t.eval(i))
    val_loss = np.array(val_loss).mean()
    print(f"validation loss for step {step}: {val_loss}")