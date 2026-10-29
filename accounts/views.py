from django.shortcuts import redirect, render

from .forms import RegistrationForm


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect('registration_success')
    else:
        form = RegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


def registration_success(request):
    return render(request, 'accounts/registration_success.html')
