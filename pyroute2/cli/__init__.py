
t_stmt = 1
t_dict = 2
t_comma = 3
t_end_of_dict = 7
t_end_of_sentence = 8
t_end_of_stream = 9


def change_pointer(f):
    f.__cli_cptr__ = True
    return f


def show_result(f):
    f.__cli_publish__ = True
    return f
