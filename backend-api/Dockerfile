FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY DwhiePaint.Api/DwhiePaint.Api.csproj DwhiePaint.Api/
RUN dotnet restore DwhiePaint.Api/DwhiePaint.Api.csproj
COPY . .
RUN dotnet publish DwhiePaint.Api/DwhiePaint.Api.csproj -c Release -o /app /p:UseAppHost=false

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS runtime
WORKDIR /app
COPY --from=build /app ./
ENV ASPNETCORE_URLS=http://+:5000
EXPOSE 5000
ENTRYPOINT ["dotnet", "DwhiePaint.Api.dll"]
