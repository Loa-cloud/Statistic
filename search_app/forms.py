from datetime import datetime
from faulthandler import disable
from django import forms
from text_app.models import  TblText, TblTextType
from user_app.models import TblUser, TblStudent, TblGroup, TblLanguage, TblStudentGroup
#from user_app.models import TblUser, TblStudent,  TblLanguage
from text_app.models import TblTag
import datetime

from multiselectfield import MultiSelectField


# уже был написан
# возвращает список групп
class StatisticForm(forms.Form):

    fields = {'group'}

    def __init__(self, language_id:int, *args, **kwargs):
        super().__init__(*args, **kwargs)

        groups = TblGroup.objects.filter(language_id = language_id).order_by('-enrollement_date').values('id_group', 'group_name', 'enrollement_date')
        if groups.exists():
            options = []        
            for group in groups:
                options.append(
                    (
                    group['id_group'],
                    group['group_name']+\
                        ' ('+str(group['enrollement_date'].year)+' \ '\
                            +str(group['enrollement_date'].year+1)+')'
                    ))
            print(options)

        self.fields['group'] = forms.ChoiceField(choices=options)

        # year_ = datetime.today().year
        # month_ = datetime.today().month 

        # if month_ < 9:
        #     initial_start_date = datetime(year_-1, 9, 1)
        # else:
        #     initial_start_date = datetime(year_, 9, 1)

        # self.fields['start_date'] = forms.DateField(initial =initial_start_date,  widget = forms.widgets.DateInput(attrs={'type': 'date'}))


class DateInput(forms.DateInput):
    input_type = 'date'

class StatisticDataForm_2(forms.Form):
    start_date = forms.DateField(initial=datetime.date.today, widget=DateInput(attrs={'class': 'form-control'}))
    end_date = forms.DateField(initial=datetime.date.today, widget=DateInput(attrs={'class': 'form-control'}))
    check_month = forms.BooleanField()
    check_year = forms.BooleanField()


    fields = ('group',
              'language',
              'token',
              'start_date',
              'end_date',
              'check_month',
              'check_year')


    #modified_date = forms.DateField(initial=datetime.date.today, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        groups = TblGroup.objects.filter().order_by('-enrollement_date').values('id_group',
                                                                                                       'group_name',
                                                                                                       'enrollement_date')
        if groups.exists():
            options = []
            for group in groups:
                options.append(
                    (
                        group['id_group'],
                        group['group_name'] + \
                        ' (' + str(group['enrollement_date'].year) + ' \ ' \
                        + str(group['enrollement_date'].year + 1) + ')'
                    ))
            #print(options)

        self.fields['group'] = forms.ChoiceField(choices=options)


        lang = [
            (0, 'Немецкий'),
            (1, 'Французский')
        ]

        #language_object = TblLanguage.objects.filter(id_language=language_id)
        language_object = TblLanguage.objects
        self.fields['language'] = forms.ModelChoiceField(queryset=language_object,
                                                         widget=forms.Select(attrs={'class': 'form-control'}))
        #self.fields['language'].initial = language_object[1]
        #self.fields['language'] = forms.ChoiceField(choices=lang)


        self.fields['token'] = forms.MultipleChoiceField(choices=options)


class CorrelationDataForm(forms.Form):
    start_date = forms.DateField(initial=datetime.date.today, widget=DateInput(attrs={'class': 'form-control'}))
    end_date = forms.DateField(initial=datetime.date.today, widget=DateInput(attrs={'class': 'form-control'}))

    fields = ['language',
              'for_who',
              'second_p',
              'errors_g',
              'errors_f',
              'end_date', ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        language_object = TblLanguage.objects.values('id_language', 'language_name')
        options = []
        for l in language_object:
            options.append((
                l['id_language'],
                l['language_name']
            ))
        self.fields['language'] = forms.ChoiceField(choices=options)

        ################

        options = [
            (0, 'Корпус'),
            (1, 'Курс'),
            (2, 'Группа'),
            (3, 'Человек'),
        ]
        self.fields['for_who'] = forms.ChoiceField(choices=options)

        options = [
            (0, 'Самооценка'),
            (1, 'Эмоциональное состояние')
        ]
        self.fields['second_p'] = forms.ChoiceField(choices=options)

        #############33

        errors_object = TblTag.objects.filter(markup_type_id=1, tag_language=1).values('id_tag', 'tag_text')
        options2 = []
        for l in errors_object:
            options2.append((
                l['id_tag'],
                l['tag_text']
            ))
        self.fields['errors_g'] = forms.MultipleChoiceField(choices=options2)

        errors_object = TblTag.objects.filter(markup_type_id=1, tag_language=2).values('id_tag', 'tag_text')
        options2 = []
        for l in errors_object:
            options2.append((
                l['id_tag'],
                l['tag_text']
            ))
        self.fields['errors_f'] = forms.MultipleChoiceField(choices=options2)


class StatisticDataForm(forms.Form):
    start_date = forms.DateField(initial=datetime.date.today, widget=DateInput(attrs={'class': 'form-control'}))
    end_date = forms.DateField(initial=datetime.date.today, widget=DateInput(attrs={'class': 'form-control'}))

    fields = ['language',
              'for_who',
              'group',
              'student',
              'errors_g',
              'errors_f',
              'end_date', ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        student_object = TblUser.objects.values('id_user', 'last_name', 'name', 'patronymic')
        options = []
        for l in student_object:
            options.append((
                l['id_user'],
                '{0} {1} {2}'.format(l['last_name'], l['name'], l['patronymic'])

            ))
        self.fields['student'] = forms.ChoiceField(choices=options)


        ################


        language_object = TblLanguage.objects.values('id_language', 'language_name')
        options = []
        for l in language_object:
            options.append((
                    l['id_language'],
                    l['language_name']
                ))
        self.fields['language'] = forms.ChoiceField(choices=options )


        ################

        options = [
            (0, 'Корпус'),
            (1, 'Курс'),
            (2, 'Группа'),
            (3, 'Человек'),
        ]
        self.fields['for_who'] = forms.ChoiceField(choices=options)


        #############33

        errors_object = TblTag.objects.filter(markup_type_id = 1, tag_language = 1).values('id_tag', 'tag_text')
        options2 = []
        for l in errors_object:
            options2.append((
                l['id_tag'],
                l['tag_text']
            ))
        self.fields['errors_g'] = forms.MultipleChoiceField(choices=options2)

        errors_object = TblTag.objects.filter(markup_type_id=1, tag_language = 2).values('id_tag', 'tag_text')
        options2 = []
        for l in errors_object:
            options2.append((
                l['id_tag'],
                l['tag_text']
            ))
        self.fields['errors_f'] = forms.MultipleChoiceField(choices=options2)



        ##############


        group_object = TblGroup.objects.filter().order_by('-enrollement_date').values('id_group','group_name', 'enrollement_date')
        options3 = []
        for group in group_object:
            options3.append(
                (
                    group['id_group'],
                    group['group_name'] + \
                    ' (' + str(group['enrollement_date'].year) + ' \ ' \
                    + str(group['enrollement_date'].year + 1) + ')'
                ))
        self.fields['group'] = forms.ChoiceField(choices=options3, initial=options3[0])





