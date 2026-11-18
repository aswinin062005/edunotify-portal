# sms_templates.py

SMS_TEMPLATES = {
    'en': {
        'pass': "Dear Parent, your ward {student_name} has PASSED in {exam_type}. Marks: {all_marks}.",
        'fail': "Dear Parent, your ward {student_name} has FAILED in {exam_type} (Failed Subject: {failed_subjects}). Marks: {all_marks}."
    },
    'ta': {
        'pass': "அன்புள்ள பெற்றோருக்கு, உங்கள் வார்டு {student_name} {exam_type} தேர்வில் தேர்ச்சி பெற்றுள்ளார். மதிப்பெண்கள்: {all_marks}.",
        'fail': "அன்புள்ள பெற்றோருக்கு, உங்கள் வார்டு {student_name} {exam_type} தேர்வில் தோல்வியடைந்துள்ளார் (தோல்வியடைந்த பாடம்: {failed_subjects}). மதிப்பெண்கள்: {all_marks}."
    },
    'kn': {
        'pass': "ಆತ್ಮೀಯ ಪೋಷಕರೇ, ನಿಮ್ಮ ಮಗು {student_name} {exam_type} ಪರೀಕ್ಷೆಯಲ್ಲಿ ತೇರ್ಗಡೆಯಾಗಿದ್ದಾರೆ. ಅಂಕಗಳು: {all_marks}.",
        'fail': "ಆತ್ಮೀಯ ಪೋಷಕರೇ, ನಿಮ್ಮ ಮಗು {student_name} {exam_type} ಪರೀಕ್ಷೆಯಲ್ಲಿ ಅನುತ್ತೀರ್ಣರಾಗಿದ್ದಾರೆ (ಅನುತ್ತೀರ್ಣ ವಿಷಯ: {failed_subjects}). ಅಂಕಗಳು: {all_marks}."
    }
}


def build_sms_message(language, status, context):
    """
    Retrieves the translated template and injects dynamic student data.
    Falls back to English if the preferred language key is missing.
    """
    # Fall back to English if language is not supported
    lang_set = SMS_TEMPLATES.get(language, SMS_TEMPLATES['en'])
    template = lang_set.get(status, SMS_TEMPLATES['en'][status])

    return template.format(**context)