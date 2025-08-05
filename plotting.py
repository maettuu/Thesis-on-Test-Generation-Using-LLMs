import matplotlib.pyplot as plt
import numpy as np

from pathlib import Path

def generate_bar_plot(config: dict) -> None:
    """
    Generates a horizontal bar chart with the given data (descending order).

    Parameters:
        config (dict): Dictionary containing data to be plotted:
            - data (dict): The data used for the plot
            - output_name (str): The name of the output file
            - fig_size (int, int): The size of the figure in a tuple
    """

    # extract data
    data, output_name, fig_size = config.values()
    output_path = Path("plots", f"{output_name}.pdf")
    top_ten = dict(sorted(data.items(), key=lambda x: x[1], reverse=True)[:10])

    # reverse order
    labels = list(top_ten.keys())[::-1]
    values = list(top_ten.values())[::-1]

    # plot settings
    plt.figure(figsize=fig_size)
    plt.xlabel("Number of Failures", fontsize=12)
    plt.grid(axis="both", linestyle="--", alpha=0.8, linewidth=0.6, zorder=1)
    plt.tick_params(axis='y', which='both', length=0)
    plt.tick_params(axis='x', direction='in')
    plt.xticks(fontsize=12)
    plt.yticks(fontsize=12)

    # remove borders
    ax = plt.gca()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # create bars
    bars = plt.barh(labels, values, zorder=2, color="#ffaf00")

    # add labels
    for bar in bars:
        width = bar.get_width()
        plt.text(width + 5, bar.get_y() + bar.get_height() / 2, f'{int(width)}', va='center', fontsize=8)

    # save
    plt.tight_layout()
    plt.savefig(output_path, format="pdf")
    plt.show()


def generate_stacked_bar_chart(config: dict) -> None:
    """
    Generates a stacked bar chart with the given data (C1-C5).

    Parameters:
        config (dict): Dictionary containing data to be plotted:
            - models (list): The list of models used
            - prompt_configs (list): The list of prompt configs C1-C5
            - model_successes (dict): The dict holding the number of successe per prompt and model
            - output_name (str): The name of the output file
    """

    # extract data
    models, prompt_configs, model_successes, output_name = config.values()
    output_path = Path("plots", f"{output_name}.pdf")

    # plot settings
    fig, ax = plt.subplots(figsize=(6, 4))
    bottom = np.zeros(len(models))
    plt.tick_params(axis='x', which='both', length=0)
    plt.tick_params(axis='y', direction='in')
    plt.xticks(fontsize=12)
    plt.yticks(fontsize=12)
    ax.set_ylabel("Number of Successes", fontsize=12)
    ax.grid(axis="both", linestyle="--", alpha=0.8, linewidth=0.6, zorder=1)

    # remove border (spines)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


    colors = ['#ffaf00', '#f46920', '#f53255', '#f857c1', '#29bdfd']

    # stacked bars
    for config, color in zip(prompt_configs, colors):
        data = model_successes[config]
        bar_segment_drawn = False
        for i, value in enumerate(data):
            if value > 0:
                label = config if not bar_segment_drawn else ""

                # create bar
                bar = ax.bar(
                    models[i],
                    value,
                    bottom=bottom[i],
                    label=label,
                    color=color,
                    zorder=3
                )

                # add label
                ax.text(
                    bar[0].get_x() + bar[0].get_width() / 2,
                    bar[0].get_y() + bar[0].get_height() / 2,
                    str(value),
                    ha='center',
                    va='center',
                    fontsize=10,
                    color='black'
                )
                bottom[i] += value
                bar_segment_drawn = True

    # legend
    ax.legend(title="Configuration", loc="upper right")

    # save
    fig.tight_layout()
    fig.savefig(output_path, format="pdf")
    plt.show()


if __name__ == '__main__':
    config_top_failures_w_pdf = {
        "data": {
            "ExpectedNotActual": 101,
            "Failed": 1,
            "FormatError": 16,
            "GulpError": 19,
            "ImportError": 125,
            "JpxError": 4,
            "MissingPDFException": 54,
            "PassToX": 78,
            "PatchFailure": 125,
            "ReferenceError": 215,
            "ResponseException": 17,
            "SyntaxError": 74,
            "TypeError": 790,
            "UnhandledPromiseRejection": 1,
            "UnknownErrorException": 1
        },
        "output_name": "top_failures_with_pdf",
        "fig_size": (10, 6)
    }

    config_failure_class_w_pdf = {
        "data": {
            "Hallucination": 1275,
            "ExternalError": 144,
            "ExpectedNotActual": 101,
            "PassToX": 78
        },
        "output_name": "failure_classification_with_pdf",
        "fig_size": (8, 4)
    }

    config_top_failures_wo_pdf = {
        "data": {
            "ExpectedNotActual": 70,
            "FormatError": 17,
            "GulpError": 24,
            "ImportError": 155,
            "InvalidPDFException": 6,
            "JpegError": 1,
            "JpxError": 4,
            "MissingPDFException": 75,
            "PassToX": 60,
            "PasswordException": 1,
            "PatchFailure": 98,
            "ReferenceError": 212,
            "ResponseException": 21,
            "SyntaxError": 84,
            "TypeError": 783,
            "XRefEntryException": 1
        },
        "output_name": "top_failures_without_pdf",
        "fig_size": (10, 6)
    }

    config_failure_class_wo_pdf = {
        "data": {
            "Hallucination": 1330,
            "ExternalError": 122,
            "ExpectedNotActual": 70,
            "PassToX": 60
        },
        "output_name": "failure_classification_without_pdf",
        "fig_size": (8, 4)
    }

    config_model_success_w_pdf = {
        "models": ['GPT-4o', 'o3-mini', 'Llama', 'DeepSeek'],
        "prompt_configs": ['C1', 'C2', 'C3', 'C4', 'C5'],
        "model_successes": {
            'C1': [16, 7, 10, 7],
            'C2': [1, 0, 1, 0],
            'C3': [6, 0, 2, 3],
            'C4': [1, 0, 2, 1],
            'C5': [0, 0, 0, 1],
        },
        "output_name": "model_success_with_pdf"
    }

    config_model_success_wo_pdf = {
        "models": ['GPT-4o', 'o3-mini', 'Llama', 'DeepSeek'],
        "prompt_configs": ['C1', 'C2', 'C3', 'C4', 'C5'],
        "model_successes": {
            'C1': [10, 7, 7, 7],
            'C2': [6, 0, 1, 2],
            'C3': [4, 0, 2, 0],
            'C4': [3, 0, 0, 2],
            'C5': [0, 0, 0, 2],
        },
        "output_name": "model_success_without_pdf"
    }

    generate_bar_plot(config_top_failures_wo_pdf)
    generate_stacked_bar_chart(config_model_success_wo_pdf)
