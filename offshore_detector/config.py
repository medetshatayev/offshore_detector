"""
Configuration and constants for the Offshore Transaction Risk Detection System.
"""
import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
DESKTOP_PATH = os.getenv('DESKTOP_PATH', os.path.join(os.path.expanduser('~'), 'Desktop'))
THRESHOLD_KZT = float(os.getenv('THRESHOLD_KZT', 5000000.0))

OFFSHORE_JURISDICTIONS = {
    'en': [
        'andorra', 'anguilla', 'antigua and barbuda', 'aruba', 'bahamas', 'bahrain',
        'barbados', 'belize', 'bermuda', 'british virgin islands', 'cayman islands',
        'cook islands', 'cyprus', 'delaware', 'dominica', 'gibraltar', 'grenada',
        'guernsey', 'hong kong', 'isle of man', 'jersey', 'liechtenstein', 'luxembourg',
        'macao', 'macau', 'malta', 'marshall islands', 'mauritius', 'monaco', 'montserrat',
        'nauru', 'netherlands antilles', 'nevis', 'nevada', 'niue', 'panama',
        'saint kitts and nevis', 'saint lucia', 'saint vincent and the grenadines',
        'samoa', 'san marino', 'seychelles', 'singapore', 'switzerland', 'turks and caicos',
        'united arab emirates', 'vanuatu', 'virgin islands', 'dubai', 'kuwait', 'qatar',
        'alderney', 'american samoa', 'bonaire', 'curacao', 'saba', 'sint eustatius',
        'sint maarten', 'sark', 'tokelau', 'wallis and futuna'
    ],
    'ru': [
        'андорра', 'ангилья', 'антигуа и барбуда', 'аруба', 'багамы', 'бахрейн',
        'барбадос', 'белиз', 'бермуды', 'британские виргинские острова', 'каймановы острова',
        'острова кука', 'кипр', 'делавэр', 'доминика', 'гибралтар', 'гренада',
        'гернси', 'гонконг', 'остров мэн', 'джерси', 'лихтенштейн', 'люксембург',
        'макао', 'мальта', 'маршалловы острова', 'маврикий', 'монако', 'монтсеррат',
        'науру', 'нидерландские антилы', 'невис', 'невада', 'ниуэ', 'панама',
        'сент-китс и невис', 'сент-люсия', 'сент-винсент и гренадины',
        'самоа', 'сан-марино', 'сейшелы', 'сингапур', 'швейцария', 'теркс и кайкос',
        'объединенные арабские эмираты', 'вануату', 'виргинские острова', 'дубай', 'кувейт', 'катар',
        'олдерни', 'американское самоа', 'бонэйр', 'кюрасао', 'саба', 'синт-эстатиус',
        'синт-мартен', 'сарк', 'токелау', 'уоллис и футуна'
    ]
}

SWIFT_COUNTRY_MAP = {
    'AD': 'andorra', 'AI': 'anguilla', 'AG': 'antigua and barbuda', 'AW': 'aruba',
    'BS': 'bahamas', 'BH': 'bahrain', 'BB': 'barbados', 'BZ': 'belize',
    'BM': 'bermuda', 'VG': 'british virgin islands', 'KY': 'cayman islands',
    'CK': 'cook islands', 'CY': 'cyprus', 'DM': 'dominica', 'GI': 'gibraltar',
    'GD': 'grenada', 'GG': 'guernsey', 'HK': 'hong kong', 'IM': 'isle of man',
    'JE': 'jersey', 'LI': 'liechtenstein', 'LU': 'luxembourg', 'MO': 'macao',
    'MT': 'malta', 'MH': 'marshall islands', 'MU': 'mauritius', 'MC': 'monaco',
    'MS': 'montserrat', 'NR': 'nauru', 'AN': 'netherlands antilles', 'NU': 'niue',
    'PA': 'panama', 'KN': 'saint kitts and nevis', 'LC': 'saint lucia',
    'VC': 'saint vincent and the grenadines', 'WS': 'samoa', 'SM': 'san marino',
    'SC': 'seychelles', 'SG': 'singapore', 'CH': 'switzerland', 'TC': 'turks and caicos',
    'AE': 'united arab emirates', 'VU': 'vanuatu', 'VI': 'virgin islands',
    'KW': 'kuwait', 'QA': 'qatar', 'US': 'united states'
}

FIELD_WEIGHTS_INCOMING = {
    'Плательщик': 0.3,
    'Банк плательщика': 0.2,
    'Адрес банка плательщика': 0.2,
    'Страна резидентства': 0.2,
    'Город': 0.1
}

FIELD_WEIGHTS_OUTGOING = {
    'Получатель': 0.2,
    'Банк получателя': 0.2,
    'Адрес банка получателя': 0.2,
    'Страна резидентства': 0.2,
    'Город': 0.1,
    'Детали платежа': 0.1
}

FIELD_TRANSLATIONS = {
    'counterparty': 'контрагент',
    'bank': 'банк',
    'country': 'страна',
    'address': 'адрес',
    'swift': 'SWIFT',
    'city': 'город',
    'details': 'детали'
}

SCENARIO_DESCRIPTIONS = {
    1: 'Входящий из офшора',
    2: 'Исходящий в офшор',
    3: 'Операции с офшорными лицами'
}
