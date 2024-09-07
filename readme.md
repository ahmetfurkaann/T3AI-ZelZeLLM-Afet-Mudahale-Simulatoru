
#t3aihackathon #T3 #TEKNOFEST #Hackathon #LLM #ZelZeLLM

![Gorsel1](https://github.com/user-attachments/assets/ab724467-24c3-4c2e-a7f3-88be27d6b37c)
<div style="text-align: right;">

![T3](https://img.shields.io/badge/T3_Vakfı-blue)
![ZelZeLLM](https://img.shields.io/badge/ZelZeLLM-purple)
![Hackathon](https://img.shields.io/badge/Hackathon-yellow)
![Deprem](https://img.shields.io/badge/Deprem_Simulatoru-black)
</div>

# 2024 TEKNOFEST T3AI Doğal Dil İşleme - ZelZeLLM Takımı Dokümentasyonu

Bu proje TEKNOFEST 2024 Antalya T3AI Hackathon Yarışması Uygulama Geliştirme Kategorisi için geliştirilmiştir.



Hackathon kapsamında gerçekleştirdiğimiz çalışmaları Türk Dili ve Türkçe Doğal Dil İşleme Literatürü için de açık kaynak olarak paylaşıyoruz. 
Projenin sunumuna göz atabilirsiniz ->[Sunum linki](https://www.canva.com/design/DAGP_DaTFE/OSgWWIgIoOgGHdMnGdwhMQ/edit?utm_content=DAGP_DaTFE&utm_campaign=designshare&utm_medium=link2&utm_source=sharebutton)

Takım: ZelZeLLM <br>
Takım ID: 2323217
___________________________________________________________________________________________________________

# MOTİVASYON 
Çalışmamızı sunmadan önce, bir ön çalışma grubunda anket yoluyla bilgi toplandı. Mersin Üniversitesinde okuyan 18-30 yaş arasında olan depremde 11 ilden birinde olan gençlere
Likert ölçekli sorular soruldu ve yanıtları analiz edildi. Anket sonuçlarına göre katılımcılar, 6 Şubat depreminin ardından acil yardım ekiplerinin olay yerine ulaşmasının çok zaman aldığı konusunda hemfikir. Dahası, gelecekteki afetlerde de benzer organizasyon sorunlarının tekrar edebileceğine dair ciddi endişeler taşımaktalar.  Genel olarak, katılımcılar afet yönetiminde organizasyonel ve teknolojik eksikliklere dikkat çekmekte ve gelecekte bu alanlarda iyileştirmelere ihtiyaç olduğunu vurgulamaktadır.

# Bir AAFAD GELDİ

Anket çalışmamız bir yana, günümüz şartlarında afet yönetimi oldukça değerli ve ülkemiz için hayati bir öneme sahiptir. Deprem gibi doğal afetlerin etkilerini en aza indirmek, afet sonrası kurtarma çalışmalarını hızlı ve etkin bir şekilde organize etmek ve insanların güvenliğini sağlamak amacıyla stratejik bir öneme sahiptir.

Projemizde bu amaçla "Deprem Simülasyonu ve Ekip Koordinasyonu" başlığı altında çalıştık. 

________________________________________________________________

## Kullanıcı Arayüzü Gösterimi: 
Simülasyon, iki yan yana harita üzerinde gösterilir. Biri risk bölgelerini içerirken, diğeri sadece ajanları ve afetzedeleri gösterir. Saha yönetim araçlarında ise saha ajanının durumunu güncellediği bir arayüz bulunmaktadır.

https://github.com/user-attachments/assets/ddd962d2-ae88-4d01-ad3c-db9fff872a54

Kullanıcı Akışı: Kullanıcı, simülasyon parametrelerini belirler (ajan sayısı, afetzede sayısı, vb.)
Risk alanları manuel veya otomatik olarak belirlenir
Simülasyon başlatılır
Simülasyon sonunda detaylı bir rapor oluşturulur

<img src="https://github.com/user-attachments/assets/abcb24a0-37b5-463c-ba31-41ccef0fdbf7" alt="image" width="700"/>

İşlem bittikten sonra detaylıca işlenen log kayıtları ve operasyon özeti, ayrı bir dosyaya raporlanır.
* Ekiplerin operasyon boyunca hangi zamanda hangi işleri icra ettikleri
* Ekiplerin kaynak kullanımları
* Ekiplerin Verimlilikleri
  Başta olmak üzere benzer özellikler kaydedilir. 

________________________________________________________________

# Dinamik Çevre

Arayüz ile, belirli elementlerin otomatik olarak oluşturulmasının yanı sıra, mahalle veya ilçelerin en otpimal simülasyonlarına ulaşmak için dinamik yapı eklendi. 

https://github.com/user-attachments/assets/b350c5da-40c8-4cf9-b7aa-95ad2f578d29

Bu yapı ile: 
Ekipleri, depremzedeleri, ekip ve depremzede önceliğini, ekip görevini, kaç depremzede olduğu gibi bilgiler manuel olarak sisteme verilebilmekte.


# Proje Kapsamında T3AI Modelini Nasıl Kullandık?

Entegrasyon Noktaları: T3AI BDM API, tweet'lerden afetzedelerin öncelik seviyelerini belirlemek için kullanılmıştır. API, her tweet için 1 (düşük) ile 4 (kritik) arasında bir öncelik seviyesi döndürür. Aynı zamanda saha araçları arasında gerçek senaryo kullanımına hazır bir  T3AI BDM API temelli parser bulunmakta.

Kullanıcı Etkileşimi: Kullanıcılar, simülasyon sırasında manuel olarak afetzede sayısını ekleyebilir ve bu afetzedelerin öncelik seviyeleri T3AI BDM API kullanılarak otomatik olarak belirlenir. Afetzedelerin otomatik eklendiği durumda da öncelik T3AI BDM API tarafından belirlenebilir.

## İyileştirme Çalışmaları: 

BDM-API Prompt Engineering: T3AI BDM API'si, afet durumlarına özgü örnek tweet'ler ve öncelik seviyeleri ile eğitilmiştir. Örnekler, düşük öncelikli yiyecek/su/barınma ihtiyaçlarından kritik durumdaki enkaz altındaki kişilere kadar çeşitli senaryoları kapsamaktadır.
Hata toleransı: API'nin cevap vermediği veya hata verdiği durumlarda, sistem 1 ile 4 arasında rastgele bir öncelik atayarak çalışmaya devam etmektedir.
Dinamik öncelik güncelleme: Afetzedelerin bekleme süreleri 50 saniyeyi aştığında, öncelik seviyeleri otomatik olarak artırılmaktadır.
Çok yönlü fayda hesaplaması: Görev atamalarında mesafe, aciliyet, bekleme süresi ve ajan rolü faktörleri dikkate alınarak kapsamlı bir fayda hesaplaması yapılmaktadır.
