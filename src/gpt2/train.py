import argparse
import torch
import torch.optim as optim
import torch.multiprocessing as mp
from .utils import amp
from .utils import fusing
from .utils import distributing
from .misc import progress
from .misc.training import Trainer
from .misc.objective import LMObjective
from .data.vocabulary import Vocab
from .data.serving import TokenizedCorpusDataset
from .modeling.transformer import Transformer

# Ignore warnings.
import warnings
warnings.filterwarnings(action='ignore')


def _main_worker(rank: int, args: argparse.Namespace):
    if args.gpus:
        distributing.initialize(idx=rank, gpus=args.gpus)

    # Prepare vocabulary and datasets.
    vocab = Vocab(vocab_path=args.vocab)
    train_dataset = TokenizedCorpusDataset(vocab,
                                           corpus_path=args.train_corpus,
                                           seq_len=args.seq_len)
    eval_dataset = TokenizedCorpusDataset(vocab,
                                          corpus_path=args.eval_corpus,
                                          seq_len=args.seq_len)

    # Create transformer model and initialize.
    model = Transformer(layers=args.layers, pad_idx=vocab.pad_idx,
                        words=len(vocab), seq_len=args.seq_len,
                        heads=args.heads, dims=args.dims, rate=args.rate,
                        dropout=args.dropout, bidirectional=False)
    if args.init_from:
        ckpt = torch.load(args.init_from, map_location='cpu')
        model.load_state_dict(ckpt['model'])

    model.cuda()

    # Create objective, optimizer, learning rate scheduler.
    objective = LMObjective(model, pad_idx=vocab.pad_idx)

    optimizer = fusing.Adam(
        model.parameters(), lr=args.base_lr, weight_decay=args.wd_rate)
    scheduler = optim.lr_scheduler.LambdaLR(
        optimizer, lambda step: 1 - step / args.iterations)

    # Prepare an integrated trainer.
    trainer = Trainer(model, optimizer, scheduler, train_dataset, eval_dataset,
                      train_objective=objective, eval_objective=objective)

    # Use automatic mixed-precision.
    if args.use_amp:
        amp.apply(trainer)

    # Use distributed training.
    if args.gpus:
        distributing.apply(trainer)

    # Restore training states from checkpoint.
    if args.resume:
        trainer.restore(args.checkpoint)

    # Start training the model.
    progressbar = progress.ProgressBar(
        trainer.iters + 1, args.iterations,
        desc='Train GPT-2', observe=trainer,
        fstring='train/loss: {train_loss:.4f}, eval/loss: {eval_loss:.4f}')

    for trainer.iters in progressbar:
        trainer.train(batch=args.batch_train)

        if (trainer.iters + 1) % args.eval_iters == 0:
            trainer.evaluate(batch=args.batch_eval)
            trainer.stamp(trainer.iters)

        if (trainer.iters + 1) % args.save_iters == 0:
            trainer.preserve(args.checkpoint)

    # Save trained model and recorded metrics.
    trainer.save_model(args.checkpoint)


def _train_gpt2_model(args: argparse.Namespace):
    if args.gpus:
        mp.spawn(_main_worker, args=(args,), nprocs=len(args.gpus))
    else:
        _main_worker(0, args)


def add_subparser(subparsers: argparse._SubParsersAction):
    parser = subparsers.add_parser('train', help='train GPT-2 model.')

    parser.add_argument('--train_corpus', required=True,
                        help='corpus file for training')
    parser.add_argument('--eval_corpus', required=True,
                        help='corpus file for evaluation')
    parser.add_argument('--vocab', required=True,
                        help='vocabulary file path')

    parser.add_argument('--init_from', default=None,
                        help='initialize weights from trained model')
    parser.add_argument('--resume', action='store_true',
                        help='resume training from the given checkpoint file')
    parser.add_argument('--checkpoint', default='ckpt',
                        help='checkpoint file path')

    parser.add_argument('--seq_len', default=64, type=int,
                        help='maximum length of sequences')
    parser.add_argument('--layers', default=12, type=int,
                        help='number of decoder layers')
    parser.add_argument('--heads', default=16, type=int,
                        help='number of multi-heads in attention')
    parser.add_argument('--dims', default=1024, type=int,
                        help='dimension of representation in each layer')
    parser.add_argument('--rate', default=4, type=int,
                        help='increase rate of dimensionality in bottleneck')
    parser.add_argument('--dropout', default=0.1, type=float,
                        help='dropout rate')

    parser.add_argument('--batch_train', default=64, type=int,
                        help='batch size for training')
    parser.add_argument('--batch_eval', default=64, type=int,
                        help='batch size for evaluation')
    parser.add_argument('--base_lr', default=1e-4, type=float,
                        help='maximum learning rate')
    parser.add_argument('--wd_rate', default=1e-2, type=float,
                        help='weight decay rate')

    parser.add_argument('--iterations', default=100000, type=int,
                        help='number of training iterations')
    parser.add_argument('--eval_iters', default=500, type=int,
                        help='period to evaluate')
    parser.add_argument('--save_iters', default=1000, type=int,
                        help='period to save training state')

    parser.add_argument('--gpus', default=None, type=int, nargs='*',
                        help='gpu ids for training')
    parser.add_argument('--use_amp', action='store_true',
                        help='use automatic mixed-precision in training')

    parser.set_defaults(func=_train_gpt2_model)
