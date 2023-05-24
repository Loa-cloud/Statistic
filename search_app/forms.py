from datetime import datetime
from faulthandler import disable
from django import forms
from text_app.models import  TblText, TblTextType
from user_app.models import TblUser, TblStudent, TblGroup, TblLanguage, TblStudentGroup
#from user_app.models import TblUser, TblStudent,  TblLanguage
from text_app.models import TblTag
import datetime

from multiselectfield import MultiSelectField


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


class DateInput(forms.DateInput):
    input_type = 'date'


# форма для страницы correlation_data.html
class CorrelationDataForm(forms.Form):
    start_date = forms.DateField(initial=datetime.date.today, widget=DateInput(attrs={'class': 'form-control'}))
    end_date = forms.DateField(initial=datetime.date.today, widget=DateInput(attrs={'class': 'form-control'}))

    fields = ['language',
              'for_who',
              'group',
              'student',
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


        options = [
            (0, 'Корпус'),
            (1, 'Курс'),
            (2, 'Группа'),
            (3, 'Человек'),
        ]
        self.fields['for_who'] = forms.ChoiceField(choices=options)

        options = [
            (0, 'Самооценка'),
            (1, 'Эмоциональное состояние'),
            (2, 'Место написания'),
            (3, 'Средство написания'),
            (4, 'Оценка задания студентом'),
        ]
        self.fields['second_p'] = forms.ChoiceField(choices=options)


        errors_object = TblTag.objects.filter(markup_type_id=1, tag_language=1).values('id_tag', 'tag_text')
        options2 = []
        for l in errors_object:
            options2.append((
                l['id_tag'],
                l['tag_text']
            ))
        self.fields['errors_g'] = forms.MultipleChoiceField(choices=options2, initial=options2[0])

        errors_object = TblTag.objects.filter(markup_type_id=1, tag_language=2).values('id_tag', 'tag_text')
        options2 = []
        for l in errors_object:
            options2.append((
                l['id_tag'],
                l['tag_text']
            ))
        self.fields['errors_f'] = forms.MultipleChoiceField(choices=options2, initial=options2[0])

        group_object = TblGroup.objects.filter().order_by('-enrollement_date').values('id_group', 'group_name',
                                                                                      'enrollement_date')
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

        student_object = TblUser.objects.values('id_user', 'last_name', 'name', 'patronymic')
        options = []
        for l in student_object:
            options.append((
                l['id_user'],
                '{0} {1} {2}'.format(l['last_name'], l['name'], l['patronymic'])

            ))
        self.fields['student'] = forms.ChoiceField(choices=options)



# форма для страницы statistic_data.html
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


        language_object = TblLanguage.objects.values('id_language', 'language_name')
        options = []
        for l in language_object:
            options.append((
                    l['id_language'],
                    l['language_name']
                ))
        self.fields['language'] = forms.ChoiceField(choices=options )


        options = [
            (0, 'Корпус'),
            (1, 'Курс'),
            (2, 'Группа'),
            (3, 'Человек'),
        ]
        self.fields['for_who'] = forms.ChoiceField(choices=options)


        errors_object = TblTag.objects.filter(markup_type_id = 1, tag_language = 1).values('id_tag', 'tag_text')
        options2 = []
        for l in errors_object:
            options2.append((
                l['id_tag'],
                l['tag_text']
            ))
        self.fields['errors_g'] = forms.MultipleChoiceField(choices=options2, initial=options2[0])


        errors_object = TblTag.objects.filter(markup_type_id=1, tag_language = 2).values('id_tag', 'tag_text')
        options2 = []
        for l in errors_object:
            options2.append((
                l['id_tag'],
                l['tag_text']
            ))
        self.fields['errors_f'] = forms.MultipleChoiceField(choices=options2, initial=options2[0])


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
