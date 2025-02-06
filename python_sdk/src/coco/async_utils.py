from typing import Callable, Awaitable, Any
import asyncio
import tqdm.asyncio


def _split_args(
    args: list[Any], kwargs: dict[str, Any], batch_size: int
) -> tuple[list[list[Any]], dict[str, list[Any]], int]:
    """Split list and keyword list arguments into batches.

    Args:
        args (list[Any]): List of arguments.
        kwargs (dict[str, Any]): Dictionary of keyword arguments.
        batch_size (int): The size of each batch.

    Returns:
        tuple[list[list[Any]], dict[str, list[Any]], int]: List of batched arguments, dictionary of batched keyword arguments, and number of batches.
    """
    n_batches = None

    # batch all list arguments
    new_args = []
    for arg in args:
        if isinstance(arg, list):
            new_args.append(
                [arg[i : i + batch_size] for i in range(0, len(arg), batch_size)]
            )
            # make sure all list arguments result in same number of batches
            if n_batches is None:
                n_batches = len(new_args[-1])
            else:
                assert n_batches == len(
                    new_args[-1]
                ), "All list arguments must result in the same number of batches"
        else:
            new_args.append([arg] * n_batches)

    # batch all keyword list arguments
    new_kwargs = {}
    for key, value in kwargs.items():
        if isinstance(value, list):
            new_kwargs[key] = [
                value[i : i + batch_size] for i in range(0, len(value), batch_size)
            ]
            # make sure all list arguments result in same number of batches
            if n_batches is None:
                n_batches = len(new_kwargs[key])
            else:
                assert n_batches == len(
                    new_kwargs[key]
                ), "All list arguments must result in the same number of batches"
        else:
            new_kwargs[key] = [value] * n_batches

    return new_args, new_kwargs, n_batches


async def _waiting_wrapper(
    function: Callable[..., Awaitable[Any]],
    args: list[Any],
    kwargs: dict[str, Any],
    semaphore: asyncio.Semaphore | None,
):
    """
    Wrapper that runs an async function
    as soon as the semaphore is available.
    """
    if semaphore is None:
        return await function(*args, **kwargs)

    async with semaphore:
        return await function(*args, **kwargs)


async def _run_batches(
    function: Callable[..., Awaitable[Any]],
    limit_parallel: int,
    new_args: list[list[Any]],
    new_kwargs: dict[str, list[Any]],
    n_batches: int,
    show_progress: bool,
    description: str | None,
):
    """
    Run function on all batches in parallel and
    aggregate results in single flattened list.
    """
    # construct list of tasks
    tasks = []
    semaphore = (
        asyncio.Semaphore(limit_parallel) if limit_parallel is not None else None
    )
    for i in range(n_batches):
        batch_args = [arg[i] for arg in new_args]
        batch_kwargs = {key: value[i] for key, value in new_kwargs.items()}
        tasks.append(_waiting_wrapper(function, batch_args, batch_kwargs, semaphore))

    if show_progress:
        results = await tqdm.asyncio.tqdm.gather(*tasks, desc=description, unit="batch")
    else:
        results = await asyncio.gather(*tasks)
    if isinstance(results[0], tuple):
        return_values = tuple([] for _ in results[0])
        for batch in results:
            for i, sublist in enumerate(batch):
                return_values[i].extend(sublist)
    else:
        return_values = [e for batch in results for e in batch]

    return return_values


def batched_parallel(
    function: Callable[..., Awaitable[Any]],
    batch_size: int,
    limit_parallel: int | None,
    show_progress: bool,
    description: str | None,
    return_async_wrapper: bool = False,
) -> Callable:
    """
    Wrapper that batches list arguments of an async function
    and runs the function on each batch in parallel.

    All list arguments of the function are batched.
    The function must either return a list or a tuple of lists.

    Args:
        function (Callable[..., Awaitable[Any]]): The function to run in parallel.
        batch_size (int): The size of each batch.
        limit_parallel (int | None): The maximum number of parallel tasks / batches.
        show_progress (bool): Whether to show a progress bar on stdout.
        description (str | None): The description of the progress bar.
        return_async_wrapper (bool): Whether to return an async wrapper.

    Returns:
        Callable: A wrapper that can be used to run the function in parallel.
    """
    if return_async_wrapper:

        async def batched_wrapper(*args, **kwargs):
            new_args, new_kwargs, n_batches = _split_args(args, kwargs, batch_size)

            # if there is only one batch, run the function directly
            if n_batches is None or n_batches == 1:
                return await function(*args, **kwargs)

            return await _run_batches(
                function=function,
                limit_parallel=limit_parallel,
                new_args=new_args,
                new_kwargs=new_kwargs,
                n_batches=n_batches,
                show_progress=show_progress,
                description=description,
            )

    else:

        def batched_wrapper(*args, **kwargs):
            new_args, new_kwargs, n_batches = _split_args(args, kwargs, batch_size)

            if n_batches is None or n_batches == 1:
                return asyncio.run(function(*args, **kwargs))

            return asyncio.run(
                _run_batches(
                    function=function,
                    limit_parallel=limit_parallel,
                    new_args=new_args,
                    new_kwargs=new_kwargs,
                    n_batches=n_batches,
                    show_progress=show_progress,
                    description=description,
                )
            )

    return batched_wrapper
