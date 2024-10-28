# python_template_module

A template module, implemented in python, for integrating a device into a WEI workcell.

## Using This Template

[Creating a Repository From a Template](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template)


## Renaming

To automatically replace `python_template` with the name of your instrument, run the "Rename Module Repo" GitHub Actions Workflow in your repository: [Manually Running a Workflow](https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-workflow-runs/manually-running-a-workflow)

N.B. this assumes your repository is named using the `<instrument_name>_module` format.

Alternatively, you can run `.github/rename.sh python_template <new_name>` locally and commit the results.

## TODO's

Throughout this module template, there are a number of comments marked `TODO`. You can use search/find and replace to help ensure you're taking full advantage of the module template and don't have any residual template artifacts hanging around.

## Guide to Writing Your Own Module

For more details on how to write your own module (either using this template or from scratch), see [How-To: Modules (WEI Docs)](https://rpl-wei.readthedocs.io/en/latest/pages/how-to/module.html)
