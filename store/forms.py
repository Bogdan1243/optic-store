from django import forms
from .models import Review, ReturnRequest
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.Select(choices=[(i, f'{i} Stars') for i in range(1, 6)], attrs={'class': 'form-select'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Write your review here...'})
        }
class CustomRegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(max_length=254, required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('first_name', 'last_name', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control rounded-0 py-2 fs-6',
            })

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un cont cu această adresă de email există deja.")
        return email


class ReturnRequestForm(forms.ModelForm):
    accept_conditions = forms.BooleanField(
        required=True,
        label="Confirm că produsele sunt în stare impecabilă, în ambalajul original complet și nu fac parte din excepțiile de la dreptul de retur (ex. lentile cu dioptrii personalizate, produse desigilate).",
        error_messages={
            'required': 'Trebuie să confirmați îndeplinirea condițiilor de retur pentru a trimite formularul.'
        }
    )

    class Meta:
        model = ReturnRequest
        fields = [
            'order_number',
            'full_name',
            'email',
            'phone',
            'products',
            'return_reason',
            'refund_method',
            'iban',
            'account_holder',
            'observations',
        ]
        widgets = {
            'order_number': forms.TextInput(attrs={
                'class': 'form-control rounded-0 py-3 px-3',
                'placeholder': 'Ex: #1024',
                'style': 'background-color: #fafafa; border: 1px solid #e5e5e5;'
            }),
            'full_name': forms.TextInput(attrs={
                'class': 'form-control rounded-0 py-3 px-3',
                'placeholder': 'Ex: Ion Popescu',
                'style': 'background-color: #fafafa; border: 1px solid #e5e5e5;'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control rounded-0 py-3 px-3',
                'placeholder': 'Ex: ion.popescu@exemplu.ro',
                'style': 'background-color: #fafafa; border: 1px solid #e5e5e5;'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control rounded-0 py-3 px-3',
                'placeholder': 'Ex: 07xx xxx xxx',
                'style': 'background-color: #fafafa; border: 1px solid #e5e5e5;'
            }),
            'products': forms.Textarea(attrs={
                'class': 'form-control rounded-0 py-3 px-3',
                'rows': 3,
                'placeholder': 'Ex: 1x Ray-Ban RB2132 Negru Mat (mărimea M)',
                'style': 'background-color: #fafafa; border: 1px solid #e5e5e5;'
            }),
            'return_reason': forms.Select(attrs={
                'class': 'form-select rounded-0 py-3 px-3',
                'style': 'background-color: #fafafa; border: 1px solid #e5e5e5;'
            }),
            'refund_method': forms.Select(attrs={
                'class': 'form-select rounded-0 py-3 px-3',
                'id': 'id_refund_method',
                'style': 'background-color: #fafafa; border: 1px solid #e5e5e5;'
            }),
            'iban': forms.TextInput(attrs={
                'class': 'form-control rounded-0 py-3 px-3',
                'placeholder': 'Ex: RO49 AAAA 1B31 0075 9384 0000',
                'style': 'background-color: #fafafa; border: 1px solid #e5e5e5;'
            }),
            'account_holder': forms.TextInput(attrs={
                'class': 'form-control rounded-0 py-3 px-3',
                'placeholder': 'Numele titularului contului bancar',
                'style': 'background-color: #fafafa; border: 1px solid #e5e5e5;'
            }),
            'observations': forms.Textarea(attrs={
                'class': 'form-control rounded-0 py-3 px-3',
                'rows': 2,
                'placeholder': 'Detalii opționale despre solicitarea dvs...',
                'style': 'background-color: #fafafa; border: 1px solid #e5e5e5;'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        refund_method = cleaned_data.get('refund_method')
        iban = (cleaned_data.get('iban') or '').strip()

        if refund_method == 'iban' and not iban:
            self.add_error('iban', 'Vă rugăm să introduceți contul IBAN pentru rambursarea prin transfer bancar.')

        return cleaned_data