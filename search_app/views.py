import re
import urllib
from datetime import datetime
from os import remove
from wsgiref.util import FileWrapper

from django.shortcuts import redirect, render
from django.http import HttpResponse
from django.utils import timezone

from django.db.models import Q
from .models import TblSystemMetric
from .forms import StatisticForm
from .stat_src import built_group_stat
from text_app.models import TblMarkup, TblToken, TblTag, TblSentence, TblText, TblTextType

from datetime import timedelta
from pakt_work_tools.custom_settings import AUTO_STAT
from text_app.models import TblMarkup, TblToken, TblTag, TblText, TblGrade
from .forms import StatisticForm
from .forms import StatisticDataForm
from .forms import CorrelationDataForm
from .stat_src import built_group_stat

import xlwt
from django.http import HttpResponse
from django.db import connection
from django.contrib.auth.models import User
#from django.utils import simplejson


def index(request):
    """ Рендер главной страницы

    Args:
        request: http-запрос с пользовательской информацией

    Returns:
        HttpResponse: html главной страницы
    """
    current_time = timezone.now()+timedelta(hours=3)
    out_metrics = []
    metrics = TblSystemMetric.objects.filter(metric_name = 'token_counter').order_by('id_metric').values().all()
    if (current_time - metrics[0]['metric_update_time']).total_seconds() >= AUTO_STAT['update_interval']:
        for index in range(len(metrics)):
            try:
                out_metrics.append(int(TblToken.objects.filter(
                    Q(sentence_id__text_id__language_id = metrics[index]['language_id'])&~Q(text = '-EMPTY-')).count()))
            except:
                out_metrics.append(0)
                
        TblSystemMetric.objects.filter(metric_name = 'token_counter').update(metric_update_time=current_time)
        TblSystemMetric.objects.filter(Q(metric_name = 'token_counter')&Q(language_id = 1)).update(metric_value=out_metrics[0])
        TblSystemMetric.objects.filter(Q(metric_name = 'token_counter')&Q(language_id = 2)).update(metric_value=out_metrics[1])

    else:
        out_metrics = [int(metrics[index]['metric_value']) for index in range(len(metrics))]

    return render(request, "index.html", context = {
        'tokens_count': {1:out_metrics[0], 2:out_metrics[1]},
        'update_time': current_time.strftime("%d.%m.%Y %H:%M:%S")
    })


def cql_faq(request):
    """ Рендер FAQ по CQL

    Args:
        request: http-запрос с пользовательской информацией

    Returns:
        HttpResponse: html FQL по CQL
    """

    return render(request, "cql_faq.html")


# суммарная статистика по ошибкам
# а также вывод этих ошибок
def _filter_shaping(cql):
    """Формирование фильтра на основе cql

    Keyword arguments:
    cql -- Запроса пользователя

    """

    # Получение аттрибута запроса
    content = re.search(r'[\'\"\”].*[\'\"\”]', cql)
    if content is not None:
        word = content.group(0)[1:-1]
    else:
        word = content

    # Удаление всех пробелов
    cql = cql.replace(" ", "")

    # Обработка токенов соответсвующих словоформе
    if 'word=' in cql:
        # REGEX
        if word[0:2] == '.*' and word[-2:] == '.*':
            return Q(token_id__text__contains=word[2:-2])
        elif word[-2:] == '.*':
            return Q(token_id__text__startswith=word[:-2])
        elif word[0:2] == '.*':
            return Q(token_id__text__endswith=word[2:])
        else:
            return Q(token_id__text__iexact=word)

    # Обрабокта токенов с указанными тегами ошибок и частеречной разметки
    elif 'error=' in cql or 'pos=' in cql:
        return Q(Q(tag_id__tag_text=word) | Q(tag_id__tag_text_russian=word) | Q(tag_id__tag_text_abbrev=word))

    # Обработка токенов с указанными степенями грубости ошибки
    elif 'grade=' in cql:
        return Q(Q(grade_id__grade_name=word) | Q(grade_id__grade_abbrev=word))

    # Обработка токенов с указанными причинами ошибки
    elif 'reason=' in cql:
        return Q(Q(reason_id__reason_name=word) | Q(reason_id__reason_abbrev=word))

    # Обработка токенов не соответсвующих словоформе
    if 'word!=' in cql:
        # REGEX
        if word[0:2] == '.*' and word[-2:] == '.*':
            return ~Q(token_id__text__contains=word[2:-2])
        elif word[-2:] == '.*':
            return ~Q(token_id__text__startswith=word[:-2])
        elif word[0:2] == '.*':
            return ~Q(token_id__text__endswith=word[2:])
        else:
            return ~Q(token_id__text__iexact=word)

    # Обрабокта токенов без указанных тегов ошибок и частеречной разметки
    elif 'error!=' in cql or 'pos!=' in cql:
        return ~Q(Q(tag_id__tag_text=word) | Q(tag_id__tag_text_russian=word) | Q(tag_id__tag_text_abbrev=word))

    # Обрабокта токенов без указанных степеней грубости ошибки
    elif 'grade!=' in cql:
        return ~Q(Q(grade_id__grade_name=word) | Q(grade_id__grade_abbrev=word))

    # Обрабокта токенов без указанных причин ошибки
    elif 'reason!=' in cql:
        return ~Q(Q(reason_id__reason_name=word) | Q(reason_id__reason_abbrev=word))

    return None


def _parse_cql(user_query=None):
    """Парсинг Corpus Query Language из запроса пользователя

    Keyword arguments:
    user_query -- Запрос пользователя (default None)

    """

    # Получение cql из запроса пользователя
    cql = re.findall(r'\[[^\[\]]+\]', user_query)

    # Формирование фильтра для поиска в БД
    filters = Q()

    for token_cql in cql:
        # TODO: парсить word не из tblmarkup
        # Парсинг нескольких параметров
        if "&" in token_cql:
            parts_token_cql = token_cql[1:-1].split('&')
            for part in parts_token_cql:

                if _filter_shaping(part) is not None:
                    filters &= _filter_shaping(part)


        # Парсинг альтернативных вариантов
        # TODO: Исправить вывод дублированных текстов(где совпадает и токен, и тег)
        elif "|" in token_cql:
            parts_token_cql = token_cql[1:-1].split('|')
            alt_filters = Q()
            for part in parts_token_cql:

                if _filter_shaping(part) is not None:
                    alt_filters |= _filter_shaping(part)

            filters &= alt_filters

        else:
            if _filter_shaping(token_cql) is not None:
                filters &= _filter_shaping(token_cql)

    if filters == Q():
        return None

    return filters


def search(request):
    """ Обработка поискового запроса пользователя и генерация результата

    Args:
        request: http-запрос с пользовательской информацией

    Returns:
        HttpResponse: html страница с результатом поиска
    """
    user_query = ""

    if request.POST:
        user_query = request.POST.get('corpus_search', "")
    else:
        user_query = request.GET.get('corpus_search', "")

    filters = _parse_cql(user_query)
    if filters is None:
        return render(request, "search.html",
                      context={'error_search': 'Text not Found', 'search_value': user_query})

    # Получение строк по заданным условиям
    sentence_objects = TblMarkup.objects.filter(filters).values(
        'token_id', 'token_id__sentence_id', 'token_id__sentence_id__text_id__header',
        'token_id__sentence_id__text_id__language_id__language_name',
        'token_id__sentence_id__text_id__text_type_id__text_type_name',
        'token_id__sentence_id__text_id__create_date', 'token_id__sentence_id__text_id'
    )

    # TODO: пропписать исключение
    if len(sentence_objects) == 0:
        return render(request, "search.html",
                      context={'error_search': 'Text not Found', 'search_value': user_query})

    # Количество найденных предложений
    count_search = len(sentence_objects)

    sentence_objects = sentence_objects

    list_search = []
    for sentence in sentence_objects:
        tokens = TblToken.objects.filter(
            sentence_id=sentence['token_id__sentence_id']
        ).order_by('order_number')

        list_token = []
        for token in tokens:
            if token.text == '-EMPTY-':
                continue
            if token.id_token == sentence['token_id']:
                list_token.append({'text': token.text, 'primary': True})
            else:
                list_token.append({'text': token.text})

        list_search.append({
            'header': sentence['token_id__sentence_id__text_id__header'],
            'language': sentence['token_id__sentence_id__text_id__language_id__language_name'],
            'text_type': sentence['token_id__sentence_id__text_id__text_type_id__text_type_name'],
            'tokens': list_token,
            'create_date': sentence['token_id__sentence_id__text_id__create_date'],
            'text_id': sentence['token_id__sentence_id__text_id'],
        })

    # Для неточного поиска
    # MyClass.objects.filter(name__iexact=my_parameter)

    return render(request, "search.html",
                  context={'search_value': user_query, 'list_search': list_search,
                           'count_search': count_search, 'is_registered': hasattr(request.user, 'id_user')})


def text(request, text_id=None):
    text_obj = TblText.objects.filter(id_text=text_id).values(
        'text', 'header', 'language_id__language_name', 'text_type_id__text_type_name'
    )

    if len(text_obj) == 0:
        return render(request, "corpus.html", context={'error_search': 'Text not Found'})

    text_obj = text_obj[0]
    text_data = re.sub(" -EMPTY- ", " ", text_obj['text'])
    header = text_obj['header']
    language = text_obj['language_id__language_name']
    text_type = text_obj['text_type_id__text_type_name']
    text_path = str(language) + '/' + str(text_type) + '/' + str(header)

    return (render(request, "search_text.html", context={'text': text_data, 'text_path': text_path, 'text_id': text_id,
                                                         'language_name': language, 'text_type_name': text_type}))


def get_stat(request):
    if request.user.is_teacher():
        if request.method != 'POST':
            return (render(request, 'stat_form.html',
                           {'right': True, 'form': StatisticForm(request.user.language_id), 'no_data': False}))
        else:
            form = StatisticForm(request.user.language_id, request.POST or None)
            if form.is_valid():

                group_id = int(form.cleaned_data['group'])

                stat_res = built_group_stat(group_id, request.user.id_user)
                if stat_res['state']:

                    response = HttpResponse(FileWrapper(open(stat_res['folder_link'], 'rb')),
                                            content_type='application/zip')

                    filename = stat_res['file_name'].replace(" ", "_")
                    response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)

                    remove(stat_res['folder_link'])
                    return response

                else:
                    return render(request, 'stat_form.html',
                                  {'right': True, 'form': StatisticForm(request.user.language_id), 'no_data': True})
    else:
        return render(request, 'stat_form.html', {'right': False, 'no_data': False})


def get_error_stats(request_data):
    # получаем список ошибок
    tags = TblTag.objects.filter(tag_language_id=1)
    grades = TblGrade.objects.filter(grade_language_id=1)
    grade1 = ""
    grade2 = ""
    grade3 = ""
    for grade in grades:
        if grade.id_grade == 1:
            grade1 = grade.grade_abbrev
            if grade1 is None:
                grade1 = grade.grade_name
        if grade.id_grade == 2:
            grade2 = grade.grade_abbrev
            if grade2 is None:
                grade2 = grade.grade_name
        if grade.id_grade == 3:
            grade3 = grade.grade_abbrev
            if grade3 is None:
                grade3 = grade.grade_name

    data = []
    for tag_item in tags:
        stat_item = {'id_tag': tag_item.id_tag, 'tag_name': tag_item.tag_text, 'tag_desc': tag_item.tag_text_russian,
                     'tag_text_abbrev': tag_item.tag_text_abbrev}
        # ищем использование ошибки
        degree1 = TblMarkup.objects.filter(tag_id=tag_item.id_tag, grade_id=1)
        stat_item["degree1_count"] = len(degree1)
        stat_item["degree1_name"] = grade1
        if len(degree1) != 0:
            stat_item["degree1_sample"] = "corpus_search=" + urllib.parse.quote(
                f"[grade=\"{grade1}\" & error=\"{tag_item.tag_text_abbrev}\"]")

        degree2 = TblMarkup.objects.filter(tag_id=tag_item.id_tag, grade_id=2)
        stat_item["degree2_count"] = len(degree2)
        stat_item["degree2_name"] = grade2
        if len(degree2) != 0:
            stat_item["degree2_sample"] = "corpus_search=" + urllib.parse.quote(
                f"[grade=\"{grade2}\" & error=\"{tag_item.tag_text_abbrev}\"]")

        degree3 = TblMarkup.objects.filter(tag_id=tag_item.id_tag, grade_id=3)
        stat_item["degree3_count"] = len(degree3)
        stat_item["degree3_name"] = grade3
        if len(degree3) != 0:
            stat_item["degree3_sample"] = "corpus_search=" + urllib.parse.quote(
                f"[grade=\"{grade3}\" & error=\"{tag_item.tag_text_abbrev}\"]")

        stat_item['is_normal'] = "none"
        if stat_item['degree1_count'] != 0 and stat_item['degree2_count'] != 0 and stat_item['degree3_count'] != 0:
            stat_item['is_normal'] = "coral"
        elif (stat_item['degree1_count'] != 0 and stat_item['degree2_count'] != 0) or \
                (stat_item['degree1_count'] != 0 and stat_item['degree3_count'] != 0) or \
                (stat_item['degree2_count'] != 0 and stat_item['degree3_count'] != 0):
            stat_item['is_normal'] = "khaki"

        data.append(stat_item)
    return render(request_data, 'error_stats.html', {'error_data': data})


def statistic_data(request):
    if request.user.is_teacher():
        context = {}
        context['right'] = True
        context['no_data'] = False
        context['categories'] = ['Ошибки']
        context['series_name'] = ['Ошибка 1', 'Ошибка 2', 'Ошибка 3']
        context['series_data'] = [[3], [1], [6]]
        error_dict = {
            1: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
            2: [27, 28, 29, 30],
            3: [31, 32, 33, 34],
            4: [35, 36, 37],
            5: [38, 39, 40, 41, 42, 43],
            6: [44, 45, 46, 47, 48],
            7: [49, 50],
            8: [51, 52, 53],
            10: [54, 55, 56, 57],
            12: [58, 59],
            14: [60, 61],
            15: [16, 17, 18],
            18: [62, 63, 64],
            19: [20, 22],
            20: [65],
            44: [67, 68, 69, 70],
            45: [71, 72],
            46: [73, 74],
            47: [75, 76, 77],
            58: [78, 79, 80, 81],
            59: [82, 83],
            71: [84, 85, 86, 87, 88],
            72: [89, 90, 91, 92, 93],
            239: [1, 15, 19, 23, 24, 25, 26],
            94: [95, 96, 97, 98, 99, 100, 101, 102, 103],
            95: [117, 118],
            96: [119, 120, 121, 122, 123, 124, 125],
            97: [126, 127],
            98: [128, 129, 130, 131, 132, 133, 134, 135],
            99: [138, 139, 140, 141, 142, 143, 144, 145],
            100: [146, 147, 148, 149],
            101: [150, 151],
            103: [136, 137],
            104: [105, 106, 107],
            108: [109, 110, 111, 112, 113, 114, 115, 116],
            139: [152, 153],
            140: [154, 155, 156, 157],
            141: [158, 159],
            143: [160, 161],
            146: [162, 163, 164],
            241: [94, 104, 108]
        }
        context['error_dict'] = error_dict

        # получение данных из формы
        if request.method == 'POST':
            form = StatisticDataForm(data=request.POST)
            if form.is_valid():
                if 'graph' in request.POST:
                    context = get_graph(context, form)
                    context['form'] = form
                    return (render(request, 'statistic_data.html', context=context))
                if 'exel' in request.POST:
                    print(form.cleaned_data['start_date'])
                    responce = statistic_data_get_exel(form)
                    return responce
            else:
                print(form.cleaned_data)
        else:
            form = StatisticDataForm()
        context['form'] = form
        return (render(request, 'statistic_data.html', context=context))
    else:
        pass


# построение графика для статистики ошибок
def get_graph(context, form):

    # ищем типы ошибок в зависимости от языка
    if form.cleaned_data['language'] == '1':
        context['series_name'] = form.cleaned_data['errors_g']
    else:
        context['series_name'] = form.cleaned_data['errors_f']
    for i in range(len(context['series_name'])):
        context['series_name'][i] = int(context['series_name'][i])

    # в зависимости от корпуса/курса/группы/человека ищем соответственные данные
    context['series_data'] = []
    if form.cleaned_data['for_who'] == '0':
        context = get_corpus(context, form)
    elif form.cleaned_data['for_who'] == '1':
        context = get_curs(context, form)
    elif form.cleaned_data['for_who'] == '2':
        context = get_group(context, form)
    elif form.cleaned_data['for_who'] == '3':
        context = get_student(context, form)

    # ищем корректные названия полей ошибок
    tag_id = context['series_name']
    context['series_name'] = []
    for id_error in tag_id:
        cursor = connection.cursor()
        cursor.execute(''' 
        select tag_text from pact.tbltag
        where id_tag = {0}'''.format(id_error))
        count0 = cursor.fetchall()
        context['series_name'].append(count0[0][0])
    return context

# поиск статистики ошибок для корпуса
def get_corpus(context, form):
    context['categories'] = ['Корпус']

    # получаем массив ошибок которые нужно подсчитать, также вложеных
    for one_type_error in context['series_name']:
        current_errors = []
        if one_type_error in context['error_dict']:
            current_errors = context['error_dict'][one_type_error]
        current_errors.append(one_type_error)
        current_errors_str = ",".join(map(str, current_errors))

        # запрос на получение ошибок для курса
        cursor = connection.cursor()
        cursor.execute(''' select sum(A.count)
            from
            (select tag_id, count(id_markup) as count
            from pact.tblmarkup, pact.tblsentence, pact.tbltext, pact.tbltag
            where
            pact.tblmarkup.sentence_id = pact.tblsentence.id_sentence and
            pact.tblsentence.text_id = pact.tbltext.id_text and
            tblmarkup.tag_id = tbltag.id_tag and
            markup_type_id = 1 and
            text_id in (
            select id_text
            from pact.tbltextgroup, pact.tbltext, pact.tblgroup
            where
            pact.tbltext.create_date >= '{1}' and
            pact.tbltext.create_date <= '{2}' and
            pact.tbltextgroup.text_id = pact.tbltext.id_text and
            pact.tblgroup.id_group = pact.tbltextgroup.group_id and
            error_tag_check = 1)
            group by tag_id) A
            where tag_id in ({0})'''.format(current_errors_str, form.cleaned_data['start_date']
                                                    , form.cleaned_data['end_date']))
        count0 = cursor.fetchall()
        arr = []
        t = count0[0][0]
        if t is None:
            t = 0
        t = int(t)
        arr.append(t)
        context['series_data'].append(arr)

    return context

# поиск статистики ошибок для курса
def get_curs(context, form):
    print('get_curs')
    context['categories'] = ['Курс 1', 'Курс 2', 'Курс 3', 'Курс 4', 'Курс 5']
    print('series_name - {}'.format(context['series_name']))
    # получаем массив ошибок которые нужно подсчитать, также вложеных
    for one_type_error in context['series_name']:
        current_errors = []
        if one_type_error in context['error_dict']:
            current_errors = context['error_dict'][one_type_error]
        current_errors.append(one_type_error)
        current_errors_str = ",".join(map(str, current_errors))
        print(current_errors_str)

        arr = []
        for i in range(1,6):
            cursor = connection.cursor()
            cursor.execute(''' select sum(A.count)  
                from  
                (select tag_id, count(id_markup) as count  
                from pact.tblmarkup, pact.tblsentence, pact.tbltext, pact.tbltag  
                where  
                pact.tblmarkup.sentence_id = pact.tblsentence.id_sentence and  
                pact.tblsentence.text_id = pact.tbltext.id_text and  
                tblmarkup.tag_id = tbltag.id_tag and  
                markup_type_id = 1 and  
                text_id in (  

                select id_text  
                from pact.tbltextgroup, pact.tbltext, pact.tblgroup  
                where  
                pact.tbltextgroup.text_id = pact.tbltext.id_text and
                pact.tblgroup.id_group = pact.tbltextgroup.group_id
                and error_tag_check = 1 and
                group_name like "_{3}_"
                union
                select id_text
                from pact.tbltext
                where
                error_tag_check = 1 and
                creation_course = {3} and
                pact.tbltext.create_date >= '{1}' and
                pact.tbltext.create_date <= '{2}' 
                )  
                group by tag_id) A  
                where tag_id in ({0})'''.format(current_errors_str, form.cleaned_data['start_date']
                                                , form.cleaned_data['end_date'], i))
            count0 = cursor.fetchall()
            t = count0[0][0]
            if t is None:
                t = 0
            t = int(t)
            print(t)
            arr.append(t)

        context['series_data'].append(arr)
        print('series_data - {}'.format(context['series_data']))
    return context

# поиск статистики ошибок для группы
def get_group(context, form):
    context['categories'] = ['Группа']

    for one_type_error in context['series_name']:
        current_errors = []
        if one_type_error in context['error_dict']:
            current_errors = context['error_dict'][one_type_error]
        current_errors.append(one_type_error)
        current_errors_str = ",".join(map(str, current_errors))

        cursor = connection.cursor()
        cursor.execute(''' select sum(A.count)
                    from
                    (select tag_id, count(id_markup) as count
                    from pakt3.tblmarkup, pakt3.tblsentence, pakt3.tbltext, pakt3.tbltag
                    where
                    pakt3.tblmarkup.sentence_id = pakt3.tblsentence.id_sentence and
                    pakt3.tblsentence.text_id = pakt3.tbltext.id_text and
                    tblmarkup.tag_id = tbltag.id_tag and
                    markup_type_id = 1 and
                    text_id in (
                    select id_text
                    from pakt3.tbltextgroup, pakt3.tbltext, pakt3.tblgroup
                    where
                    pakt3.tblgroup.id_group = {3} and
                    pakt3.tbltextgroup.text_id = pakt3.tbltext.id_text and
                    pakt3.tblgroup.id_group = pakt3.tbltextgroup.group_id and
                    error_tag_check = 1)
                    group by tag_id) A
                    where tag_id in ({0})'''.format(current_errors_str, form.cleaned_data['start_date'],
                                                    form.cleaned_data['end_date'], int(form.cleaned_data['group'])))
        count0 = cursor.fetchall()
        arr = []

        t = count0[0][0]
        if t is None:
            t = 0
        t = int(t)
        arr.append(t)
        context['series_data'].append(arr)

        # получение названия группы
        cursor = connection.cursor()
        cursor.execute('''
        select group_name, enrollement_date
        from pakt3.tblgroup
        where id_group = {0}
        '''.format(int(form.cleaned_data['group'])))
        count0 = cursor.fetchall()
        t = '{0} ({1})'.format(count0[0][0], count0[0][1])
        arr = []
        arr.append(t)
        context['categories'] = arr
    return context

# поиск статистики ошибок для студента
def get_student(context, form):
    context['categories'] = form.cleaned_data['student']

    # получаем массив ошибок которые нужно подсчитать, также вложеных
    for one_type_error in context['series_name']:
        current_errors = []
        if one_type_error in context['error_dict']:
            current_errors = context['error_dict'][one_type_error]
        current_errors.append(one_type_error)
        current_errors_str = ",".join(map(str, current_errors))

        cursor = connection.cursor()
        cursor.execute(''' select sum(A.count)
                from
                (select tag_id, count(id_markup) as count
                from pakt3.tblmarkup, pakt3.tblsentence, pakt3.tbltext, pakt3.tbltag
                where
                pakt3.tblmarkup.sentence_id = pakt3.tblsentence.id_sentence and
                pakt3.tblsentence.text_id = pakt3.tbltext.id_text and
                tblmarkup.tag_id = tbltag.id_tag and
                markup_type_id = 1 and
                text_id in (
                select id_text
                from pakt3.tbltextgroup, pakt3.tbltext, pakt3.tblgroup
                where
                pakt3.tbltext.user_id = {3} and
                pakt3.tbltext.create_date >= '{1}' and
                pakt3.tbltext.create_date <= '{2}' and
                pakt3.tbltextgroup.text_id = pakt3.tbltext.id_text and
                pakt3.tblgroup.id_group = pakt3.tbltextgroup.group_id and
                error_tag_check = 1
                )
                group by tag_id) A
                where tag_id in ({0})'''.format(current_errors_str, form.cleaned_data['start_date']
                                                , form.cleaned_data['end_date'], form.cleaned_data['student']))
        count0 = cursor.fetchall()
        arr = []
        t = count0[0][0]
        if t is None:
            t = 0
        t = int(t)
        arr.append(t)
        context['series_data'].append(arr)

        # получение фио студента
        cursor = connection.cursor()
        cursor.execute('''
                select last_name, name, patronymic
                from pakt3.tbluser
                where id_user = {0}
                '''.format(int(form.cleaned_data['student'])))
        count0 = cursor.fetchall()
        t = '{0} {1} {2}'.format(count0[0][0], count0[0][1], count0[0][2])
        arr = []
        arr.append(t)
        context['categories'] = arr
    return context


def statistic_data_get_exel(form):
    id_language = form.cleaned_data['language']
    start_date = form.cleaned_data['start_date']
    end_date = form.cleaned_data['end_date']
    if form.cleaned_data['language'] == 1:
        errors_tag = form.cleaned_data['errors_g']
    else:
        errors_tag = form.cleaned_data['errors_f']

    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename="test_token.xls"'
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('Users Data')  # this will make a sheet named Users Data
    row_num = 0
    font_style = xlwt.XFStyle()
    font_style.font.bold = True

    # названия колонок
    columns = ['text id', 'text header', 'text type', 'token', 'errors', 'errors/100 token']
    for i in errors_tag:
        print(i)
    for col_num in range(len(columns)):
        ws.write(row_num, col_num, columns[col_num], font_style)  # at 0 row 0 column

    styles = [xlwt.easyxf(num_format_str='yyyy-mm-dd'),
              xlwt.Style.default_style,
              ]
    styl = xlwt.Style.default_style


    cursor = connection.cursor()
    cursor.execute('''
                select tbl1.text_id, header, text_type_name, tbl1.c_tok, tbl2.count_markup, (tbl2.count_markup/(tbl1.c_tok/100))
                from
                (select distinct text_id, sum(count(pact.tbltoken.order_number)) over(PARTITION BY text_id) as c_tok
                from pact.tbltoken, pact.tblsentence, pact.tbltext
                where
                pact.tblsentence.text_id = pact.tbltext.id_text and
                pact.tbltoken.sentence_id = pact.tblsentence.id_sentence and
                text_id in
                    (
                    select id_text
                    from pact.tbltext
                    where
                    tbltext.language_id = {0} and error_tag_check = 1
                    and tbltext.create_date >= '{1}'
                    and tbltext.create_date <= '{2}'
                    )
                group by sentence_id) tbl1,
                
                (select pact.tbltext.id_text as id, sum(case when A.id_m = 1 then 1 else 0 end) as count_markup
                from(
                    select distinct id_text, pact.tbltext.self_rating, pact.tblmarkup.id_markup, markup_type_id as id_m
                    from pact.tbltext, pact.tblsentence, pact.tblmarkup, pact.tbltag
                    where
                    pact.tblmarkup.sentence_id = pact.tblsentence.id_sentence and
                    pact.tblsentence.text_id = pact.tbltext.id_text and
                    tblmarkup.tag_id = tbltag.id_tag and
                    tbltext.language_id = {0} and error_tag_check = 1) as A
                , pact.tbltext
                where pact.tbltext.id_text = A.id_text
                group by pact.tbltext.id_text
                ) tbl2, pact.tbltext, pact.tbltexttype
                where
                tbl1.text_id = tbl2.id and tbltexttype.id_text_type = tbltext.text_type_id
                and tbltext.id_text = tbl2.id
                '''.format(id_language, start_date, end_date))
    rows = cursor.fetchall()

    for row in rows:
        row_num += 1
        for col_num in range(len(row)):
            ws.write(row_num, col_num, row[col_num], styl)

    wb.save(response)
    return response




def correlation_data(request):
    if request.user.is_teacher():
        context = {}
        context['right'] = True
        context['no_data'] = False
        context['categories'] = ['Ошибки']
        context['series_name'] = ['Ошибка 1', 'Ошибка 2', 'Ошибка 3']
        context['series_data'] = [[3], [1], [6]]
        error_dict = {
            1: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
            2: [27, 28, 29, 30],
            3: [31, 32, 33, 34],
            4: [35, 36, 37],
            5: [38, 39, 40, 41, 42, 43],
            6: [44, 45, 46, 47, 48],
            7: [49, 50],
            8: [51, 52, 53],
            10: [54, 55, 56, 57],
            12: [58, 59],
            14: [60, 61],
            15: [16, 17, 18],
            18: [62, 63, 64],
            19: [20, 22],
            20: [65],
            44: [67, 68, 69, 70],
            45: [71, 72],
            46: [73, 74],
            47: [75, 76, 77],
            58: [78, 79, 80, 81],
            59: [82, 83],
            71: [84, 85, 86, 87, 88],
            72: [89, 90, 91, 92, 93],
            239: [1, 15, 19, 23, 24, 25, 26],
            94: [95, 96, 97, 98, 99, 100, 101, 102, 103],
            95: [117, 118],
            96: [119, 120, 121, 122, 123, 124, 125],
            97: [126, 127],
            98: [128, 129, 130, 131, 132, 133, 134, 135],
            99: [138, 139, 140, 141, 142, 143, 144, 145],
            100: [146, 147, 148, 149],
            101: [150, 151],
            103: [136, 137],
            104: [105, 106, 107],
            108: [109, 110, 111, 112, 113, 114, 115, 116],
            139: [152, 153],
            140: [154, 155, 156, 157],
            141: [158, 159],
            143: [160, 161],
            146: [162, 163, 164],
            241: [94, 104, 108]
        }
        context['error_dict'] = error_dict

        # получение данных из формы
        if request.method == 'POST':
            print('hi post')
            form = CorrelationDataForm(data=request.POST)
            if form.is_valid():
                print('valid')
                if 'graph' in request.POST:
                    context = get_graph_correlation(context, form)
                    context['form'] = form
                    return (render(request, 'correlation_data.html', context=context))
                if 'exel' in request.POST:
                    responce = statistic_data_get_exel(form)
                    return responce
            else:
                print(form.cleaned_data)
        else:
            form = CorrelationDataForm()
        context['form'] = form
        return (render(request, 'correlation_data.html', context=context))
    else:
        pass

# построение графика корреляции
def get_graph_correlation(context, form):
    print('get_graph_correlation')

    # ищем типы ошибок в зависимости от языка
    if form.cleaned_data['language'] == '1':
        context['series_name'] = form.cleaned_data['errors_g']
    else:
        context['series_name'] = form.cleaned_data['errors_f']
    for i in range(len(context['series_name'])):
        context['series_name'][i] = int(context['series_name'][i])
    print(context['series_name'])

    current_errors = []
    for one_type_error in context['series_name']:
        # получаем массив ошибок которые нужно подсчитать, также вложеных
        if one_type_error in context['error_dict']:
            current_errors.append(context['error_dict'][one_type_error])
        current_errors.append(one_type_error)
    current_errors_str = ",".join(map(str, current_errors))
    context['current_errors_str'] = current_errors_str.replace('[', ' ').replace(']', ' ')

    second_p = 'self_rating'
    context['yAxis'] = 'Текст к оси'
    # смотрим какой второй параметр был запрошен
    if form.cleaned_data['second_p'] == '0':
        context['yAxis'] = 'Самооценка'
        context['second_p'] = 'self_rating'
    elif form.cleaned_data['second_p'] == '1':
        context['yAxis'] = 'Эмоциональное состояние'
        context['second_p'] = 'emotional_id'
    elif form.cleaned_data['second_p'] == '2':
        context['yAxis'] = 'Место написания'
        context['second_p'] = 'write_place_id'
    elif form.cleaned_data['second_p'] == '3':
        context['yAxis'] = 'Средство написания'
        context['second_p'] = 'write_tool_id'
    elif form.cleaned_data['second_p'] == '4':
        context['yAxis'] = 'Оценка задания студентом'
        context['second_p'] = 'student_assesment'


    # ищем корреляцию в зависимости от курса/курса/группы/студента
    context['series_data'] = []
    if form.cleaned_data['for_who'] == '0':
        context = get_corpus_correlation(context, form)
    elif form.cleaned_data['for_who'] == '1':
        #context = get_cours_correlation(context, form)
        context = get_corpus_correlation(context, form)
    elif form.cleaned_data['for_who'] == '2':
        context = get_group_correlation(context, form)
    elif form.cleaned_data['for_who'] == '3':
        context = get_student_correlation(context, form)
    tag_id = context['series_name']
    context['series_name'] = []

    point_arr = []
    # запрос по каждому тексту на количество ошибок
    for text in context['text_all']:
        cursor = connection.cursor()
        cursor.execute(''' select sum(A.count)  
            from  
            (select tag_id, count(id_markup) as count  
            from pact.tblmarkup, pact.tblsentence, pact.tbltext, pact.tbltag  
            where  
            pact.tblmarkup.sentence_id = pact.tblsentence.id_sentence and  
            pact.tblsentence.text_id = pact.tbltext.id_text and  
            tblmarkup.tag_id = tbltag.id_tag and  
            markup_type_id = 1 and  
            text_id in ( {1} )  
            group by tag_id) A  
            where tag_id in ({0})'''.format(context['current_errors_str'], text[0]))
        count0 = cursor.fetchall()
        print(count0[0][0])

        arr = []
        t = count0[0][0]  # это количество ошибок
        if t is None:
            t = 0
        t = int(t)
        tt = t / (text[2] / 100)
        arr.append(float(str(round(tt, 2))))
        if text[1] is None:
            arr.append(-1)
        else:
            arr.append(text[1])
        point_arr.append(arr)
    context['series_data'] = point_arr

    return context

# поиск корреляции для корпуса
def get_corpus_correlation(context, form):
    #context['categories'] = ['Ошибки']

    # запрос на идентификаторы текстов и их второй параметр
    cursor = connection.cursor()
    cursor.execute(''' 
    select pact.tbltext.id_text, {3}, Count.S
    from pact.tbltext,
    (select distinct pact.tbltext.id_text,
    sum(count(pact.tbltoken.order_number)) over(PARTITION BY id_text) as S
    from pact.tbltoken, pact.tblsentence, pact.tbltext
    where
    pact.tblsentence.text_id = pact.tbltext.id_text and
    pact.tbltoken.sentence_id = pact.tblsentence.id_sentence and
    id_text in (
    select id_text
    from pact.tbltext
    where
    error_tag_check = 1 and
    {3} <> -1 and {3} is not null and
    language_id = {0}
    and pact.tbltext.create_date >= '{1}' and  
    pact.tbltext.create_date <= '{2}' 
    )
    group by pact.tbltoken.sentence_id) as Count
    where
    Count.id_text = pact.tbltext.id_text
    '''.format(form.cleaned_data['language'],
               form.cleaned_data['start_date'], form.cleaned_data['end_date'], context['second_p']))
    context['text_all'] = cursor.fetchall()


    return context


def get_cours_correlation(context, form):
    return context

# поиск корреляции для группы
def get_group_correlation(context, form):
    cursor = connection.cursor()
    cursor.execute(''' 
        select pact.tbltext.id_text, {3}, Count.S
        from pact.tbltext,
        (select distinct pact.tbltext.id_text,
        sum(count(pact.tbltoken.order_number)) over(PARTITION BY id_text) as S
        from pact.tbltoken, pact.tblsentence, pact.tbltext
        where
        pact.tblsentence.text_id = pact.tbltext.id_text and
        pact.tbltoken.sentence_id = pact.tblsentence.id_sentence and
        id_text in (
        select id_text
        from pact.tbltextgroup, pact.tbltext, pact.tblgroup
        where
        pact.tblgroup.id_group = {4} and
        pact.tbltextgroup.text_id = pact.tbltext.id_text and
        pact.tblgroup.id_group = pact.tbltextgroup.group_id and
        error_tag_check = 1 and
        {3} <> -1 and {3} is not null and
        tbltext.language_id = {0}
        and pact.tbltext.create_date >= '{1}' and  
        pact.tbltext.create_date <= '{2}' 
        )
        group by pact.tbltoken.sentence_id) as Count
        where
        Count.id_text = pact.tbltext.id_text
        '''.format(form.cleaned_data['language'],
                   form.cleaned_data['start_date'], form.cleaned_data['end_date'], context['second_p'], form.cleaned_data['group']))
    context['text_all'] = cursor.fetchall()
    return context

# поиск корреляции для студента
def get_student_correlation(context, form):
    cursor = connection.cursor()
    cursor.execute(''' 
            select pact.tbltext.id_text, {3}, Count.S
            from pact.tbltext,
            (select distinct pact.tbltext.id_text,
            sum(count(pact.tbltoken.order_number)) over(PARTITION BY id_text) as S
            from pact.tbltoken, pact.tblsentence, pact.tbltext
            where
            pact.tblsentence.text_id = pact.tbltext.id_text and
            pact.tbltoken.sentence_id = pact.tblsentence.id_sentence and
            id_text in (
            select id_text
            from pact.tbltextgroup, pact.tbltext
            where
            pact.tbltext.user_id = {4} and
            error_tag_check = 1 and
            {3} <> -1 and {3} is not null and
            tbltext.language_id = {0}
            and pact.tbltext.create_date >= '{1}' and  
            pact.tbltext.create_date <= '{2}' 
            )
            group by pact.tbltoken.sentence_id) as Count
            where
            Count.id_text = pact.tbltext.id_text
            '''.format(form.cleaned_data['language'],
                       form.cleaned_data['start_date'], form.cleaned_data['end_date'], context['second_p'],
                       form.cleaned_data['student']))
    context['text_all'] = cursor.fetchall()
    return context
