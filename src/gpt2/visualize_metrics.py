import torch
import argparse
import matplotlib.pyplot as plt


def visualize_recorded_metrics(args: argparse.Namespace):
    metrics = torch.load(args.model)['metrics']
    eval_steps, eval_metrics = zip(*metrics['eval/loss'])
    train_steps, train_metrics = zip(*metrics['train/loss'])

    plt.figure(figsize=(12, 8))

    plt.subplot(221)
    plt.plot(eval_steps, eval_metrics, label='evaluation')
    plt.plot(train_steps, train_metrics, label='training')
    plt.title('Cross-Entropy Loss')
    plt.xlabel('Iterations')
    plt.ylabel('Loss')
    plt.legend(loc='top right')

    plt.subplot(222)
    plt.plot(eval_steps, eval_metrics, label='evaluation')
    plt.plot(train_steps, train_metrics, label='training')
    plt.xscale('log')
    plt.title('Log-Scale Cross-Entropy Loss')
    plt.xlabel('Iterations (Log Scale)')
    plt.ylabel('Loss')
    plt.legend(loc='top right')

    target_range_train = len(train_steps) * 9 // 10
    target_range_eval = len(eval_steps) * 9 // 10
    min_loss = min(train_metrics[-target_range_train:]
                   + eval_metrics[-target_range_eval:])
    max_loss = max(train_metrics[-target_range_train:]
                   + eval_metrics[-target_range_eval:])

    plt.subplot(223)
    plt.plot(eval_steps, eval_metrics, label='evaluation')
    plt.plot(train_steps, train_metrics, label='training')
    plt.title('Loss')
    plt.xlabel('Iterations')
    plt.ylabel('Loss')
    plt.legend(loc='top right')
    plt.ylim((min_loss - 0.1, max_loss + 0.1))

    target_range_train = len(train_steps) * 3 // 10
    target_range_eval = len(eval_steps) * 3 // 10

    plt.subplot(224)
    plt.plot(eval_steps[-target_range_eval:],
             eval_metrics[-target_range_eval:],
             label='evaluation')
    plt.plot(train_steps[-target_range_train:],
             train_metrics[-target_range_train:],
             label='training')
    plt.title('Loss')
    plt.xlabel('Iterations')
    plt.ylabel('Loss')
    plt.legend(loc='top right')

    plt.tight_layout()
    if args.interactive:
        plt.show()
    else:
        plt.savefig(args.figure)


def add_subparser(subparsers: argparse._SubParsersAction):
    parser = subparsers.add_parser(
        'visualize', help='visualize metrics recorded during training')

    parser.add_argument('--figure', default='figure.png',
                        help='output figure image file path')
    parser.add_argument('--model', required=True,
                        help='trained GPT-2 model file path')
    parser.add_argument('--interactive', action='store_true',
                        help='show interactive plot window')

    parser.set_defaults(func=visualize_recorded_metrics)
