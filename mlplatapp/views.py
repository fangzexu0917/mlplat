from django.shortcuts import render, render_to_response, HttpResponse, HttpResponseRedirect, redirect, reverse
from django.http import FileResponse, StreamingHttpResponse
from django.utils import timezone
from . import utils, models
from mlplat import settings
# Create your views here.
import pandas as pd
import os
import json
import pymongo
from .feature_select import BPSO_FK, GA_FK

HOST = 'localhost'
PORT = 27017
DATABASE = 'materialsData'
DESC_INFO_DATABASE = 'colDescription'
SAMPLE_DESC_INFO_DATABASE = 'sampleDescription'
si = 0  # 暂时，用于记录第一个数值型数据的列下标
model = None


def test(request):  # for html testing
    return render(request, 'testhtml.html')


def edit(request, name, number):
    """
    由qualitycontrol页面进入的数据修改功能
    :param request:
    :param name: 数据集的名称
    :param number: 数据的NO编号
    :return:
    """
    if request.method == 'POST':
        val_list = request.POST.getlist('material_attr')  # 获取form表单数据皆为字符串，须对数字进行转换
        eval_val_list = [eval(item) if utils.is_number(item) else item for item in val_list]

        data = models.ReadData(name, HOST, PORT, DATABASE)
        key_list = []
        for k, v in data[0].items():
            key_list.append(k)
        newdata = dict(zip(key_list, eval_val_list))

        update_result = models.UpdateData({'NO': number}, {'$set': newdata}, name, HOST, PORT, DATABASE)

        return redirect(reverse('qualitycontrol', kwargs={'data_name': name}))

    if request.method == 'GET':
        # 根据数据集的名称name，编号number，查询到需要改动的数据
        data = models.ReadData(name, HOST, PORT, DATABASE)

        item = None
        for it in data:
            if it['NO'] == number:
                item = it
                break

        return render(request, 'modify_data.html', {'dataitem': item, 'dataname': name, 'col_start': si})


def setverbose(request, name, number, method):
    """
    由qualitycontrol页面进入的冗余属性标记功能
    :param request:
    :param name: 数据集名
    :param number: 页面上属性对的编号，对应冗余属性对（list）的下标
    :param method: 相关系数类型
    :return:
    """
    if request.method == 'GET':
        data = models.ReadData(name, host=HOST, port=PORT, database=DATABASE)

        excelproc = utils.excelProcessor(data)
        corr = excelproc.get_corr_coef(method)
        attr_name = excelproc.col_name[:-1]
        corr = [(attr_name[i[0]], attr_name[i[1]], i[2]) for i in corr]  # 将属性下标转为属性名
        corr.sort(key=lambda x: x[2], reverse=True)

        return render(request, 'set_verbose.html', {
            'dataname': name,
            'attrpair': corr[number],
            'corr_method': method,
        })

    if request.method == 'POST':
        ck_attr1 = request.POST.get('attr1')
        ck_attr2 = request.POST.get('attr2')

        cl = pymongo.MongoClient(host=HOST, port=PORT)
        db = cl.get_database(DATABASE)
        coll = db.get_collection('verbose_attr_' + name)

        if ck_attr1:
            coll.update_one({'name': ck_attr1}, {'$setOnInsert': {'name': ck_attr1}}, upsert=True)
        if ck_attr2:
            coll.update_one({'name': ck_attr2}, {'$setOnInsert': {'name': ck_attr2}}, upsert=True)

        return redirect(reverse('qualitycontrol', kwargs={'data_name': name}))


def index(request):
    return render(request, 'home_page.html')


def show(request):
    """
    展示数据库中的现有数据集
    :param request:
    :return:
    """
    if request.method == 'POST':
        pass

    if request.method == 'GET':
        # Data objects 有models中定义的属性
        model_info = models.Data.objects.all()  # return type: QuerySet of Data object
        # materialsData 中存在的集合
        data_info = models.ReadColl(host=HOST, port=PORT, database=DATABASE)
        data_desc_info = models.ReadColl(host=HOST, port=PORT, database=DESC_INFO_DATABASE)

        # 判断materialsData中的集合信息是否与Data表中信息一致
        # 一致则保留，否则视作冗余信息，删除
        for model_item in model_info:
            if model_item.data_name in data_info:
                continue
            else:
                models.Data.objects.filter(data_name=model_item.data_name, pub_date=model_item.pub_date).delete()

        for data_item in data_info:
            if models.Data.objects.filter(data_name=data_item):
                continue
            else:
                models.DropColl(data_item, host=HOST, port=PORT, database=DATABASE)
                models.DropColl(data_item, host=HOST, port=PORT, database=SAMPLE_DESC_INFO_DATABASE)
                models.DropColl('stat_data_quality_' + data_item, host=HOST, port=PORT,
                                database=DATABASE)  # 质量检测过程的中间结果，使用过就没用了，删除
                models.DropColl('algo_data_quality_' + data_item, host=HOST, port=PORT, database=DATABASE)
                models.DropColl('eudist_data_quality_' + data_item, host=HOST, port=PORT, database=DATABASE)

        return render(request, 'show_data.html', {'dataset': models.Data.objects.all()})


def data(request, name):
    """
    直接给出数据库中的数据，用于ajax
    :param request:
    :param name: 数据集名
    :return:
    """
    if request.method == 'GET':
        data = models.ReadData(name, host=HOST, port=PORT, database=DATABASE)
        # return HttpResponse(data)
        sample_data = models.ReadData(name, host=HOST, port=PORT, database=SAMPLE_DESC_INFO_DATABASE)
        dim_data = models.ReadData(name, host=HOST, port=PORT, database=DESC_INFO_DATABASE)
        return render(request, 'data_detail.html', {
            'data': data,
            'sampleData': sample_data,
            'dimData': dim_data,
        })


def info(request, name):
    """
    由show页面进入，展示数据集的相关描述信息
    :param request:
    :param name:
    :return:
    """
    if request.method == 'GET':
        desc_info = models.ReadData(dataName=name, host=HOST, port=PORT, database=DESC_INFO_DATABASE)
        return render(request, 'data_info.html',
                      {'dataitem': models.Data.objects.filter(data_name=name), 'descinfo': desc_info})


def download_example(request, file_name):
    """

    :param request:
    :param file_name:
    :return:
    """
    the_file_name = os.path.join(settings.BASE_DIR, 'example_file', file_name)
    response = FileResponse(open(the_file_name, 'rb'))  # 这里创建返回
    response['Content-Type'] = 'application/octet-stream'  # 注意格式
    response['Content-Disposition'] = 'attachment;filename=' + file_name  # 注意filename 这个是下载后的名字
    return response


def upload(request):
    global si
    if request.method == 'POST':
        fileinput = request.FILES.get('input-excel')  # read file from <input name="input-excel"> 数据文件
        fileinputname = fileinput.name  # get file name
        excelproc = utils.excelProcessor(fileinput)  # preprocess the file uploaded

        # descfileinput = request.FILES.get('input-excel-numAndName')  # 描述文件(目前不需要，通过网页上传描述符)

        si = excelproc.col_start
        if excelproc.has_blank_cell():  # if any blank cell exists, interrupt the uploading
            return HttpResponse('Blank Cells Exist!')

        # 将表格数据存入数据库，返回表格数据在数据库中的集合名和文档_id
        # 数据库文档不允许字段名中存在'.','$'字符，须过滤
        data_name_in_db, res = models.SavaData(fileinputname, excelproc.get_data(), True,
                                               host=HOST, port=PORT, database=DATABASE)

        # if descfileinput: #同上(目前不需要，通过网页上传描述符)
        #     descexcelproc = utils.excelProcessor(descfileinput)
        #     _, _ = models.SavaData(data_name_in_db, descexcelproc.get_data(), True, host=HOST, port=PORT,
        #                            database=SAMPLE_DESC_INFO_DATABASE)

        # 将网页上的样本描述信息和相关文祥分别存入数据库和服务器中
        sample_num = request.POST.getlist('sampleNum')
        sample_name = request.POST.getlist('sampleName')
        sample_source = request.POST.getlist('sampleSource')
        sample_desc = request.FILES.getlist('input-pdf')
        sample_desc_list = []
        for i in range(len(sample_num)):
            temp_name = 'unknown'
            if i < len(sample_desc):
                temp_name = sample_desc[i].name
                temp_filename = os.path.join(settings.MEDIA_ROOT, temp_name)
                with open(temp_filename, 'wb') as tf:
                    for file_data in sample_desc[i].chunks():
                        tf.write(file_data)
            sample_desc_list.append({
                '编号': sample_num[i],
                '名称': sample_name[i],
                '来源': sample_source[i],
                '相关文献': temp_name,
            })
        _, _ = models.SavaData(data_name_in_db, sample_desc_list, True, host=HOST, port=PORT,
                               database=SAMPLE_DESC_INFO_DATABASE)

        # 数据质量检测结果存入数据库
        # 数据质量检测结果仅作为中间数据存储，数据库不保留这些信息

        data_abstract = request.POST.get('data_abstract')
        data_keywords = request.POST.get('data_keywords').split(';')
        data_field = request.POST.get('domainType')
        data_interest = request.POST.get('areaType')
        sample_num = request.POST.get('data_size_m')
        dim_num = request.POST.get('data_size_n')
        data_type = request.POST.getlist('dataType')
        dim_range = request.POST.getlist('dimRange')
        dim_desc = request.POST.getlist('dimDesc')
        col_name = excelproc.col_name
        dim_desc_dict = []

        # firstElem = True
        for e in col_name:
            # if firstElem:
            #     firstElem = False
            #     continue
            dim_desc_dict.append({
                '名称': e,
                '数据类型': data_type[col_name.index(e)],
                '取值范围': dim_range[col_name.index(e)],
                '描述信息': dim_desc[col_name.index(e)],
            })
        _, _ = models.SavaData(data_name_in_db, dim_desc_dict, True, host=HOST, port=PORT,
                               database=DESC_INFO_DATABASE)

        submitter = request.POST.get('submmitter')
        collater = request.POST.get('proofreader')
        submitter_organization = request.POST.get('submmitter_orgnization')
        submitter_email = request.POST.get('submmitter_email')
        submitter_phone = request.POST.get('submmitter_phone')
        submitter_address = request.POST.get('submmitter_address')

        origin = request.POST.get('div_select')
        origin_type = request.POST.get('div_select1')
        origin_decision = request.POST.get('eKeyElemColumn')
        origin_platenumber = request.POST.get('eMaterialTrademark')
        origin_materialname = request.POST.get('eMName')
        origin_expcondition = request.POST.get('expconName')
        origin_exparguments = request.POST.get('expParasetting')
        origin_expdevice = request.POST.get('expDeviceName')

        modeldata = models.Data(
            data_name=data_name_in_db,
            data_abstract=data_abstract,
            data_keywords=data_keywords,
            data_field=data_field,
            data_interest=data_interest,
            sample_num=sample_num,
            dim_num=dim_num,
            submitter=submitter,
            collater=collater,
            submitter_email=submitter_email,
            submitter_phone=submitter_phone,
            submitter_organization=submitter_organization,
            submitter_address=submitter_address,
            origin=origin,
            origin_type=origin_type,
            origin_decision=origin_decision,
            origin_platenumber=origin_platenumber,
            origin_materialname=origin_materialname,
            origin_expcondition=origin_expcondition,
            origin_exparguments=origin_exparguments,
            origin_expdevice=origin_expdevice,
            pub_date=timezone.now())
        modeldata.save()

        return redirect(reverse('qualitycontrol', kwargs={
            'data_name': data_name_in_db,
            # 'stat_quality_name': stat_data_quality_name,
            # 'algo_quality_name': algo_data_quality_name,
            # 'eudist_quality_name': eudist_data_quality_name,

        }))

    if request.method == 'GET':
        return render(request, 'upload_data.html')


def qualitycontrol(request, data_name):  # , stat_quality_name, algo_quality_name, eudist_quality_name
    if request.method == 'POST':
        pass

    if request.method == 'GET':
        data = models.ReadData(data_name, host=HOST, port=PORT, database=DATABASE)

        excelproc = utils.excelProcessor(data)
        pearson_corr = excelproc.get_corr_coef('pearson')
        kendall_corr = excelproc.get_corr_coef('kendall')
        spearman_corr = excelproc.get_corr_coef('spearman')
        attr_name = excelproc.col_name[:-1]
        pearson_corr = [[attr_name[i[0]], attr_name[i[1]], i[2]] for i in pearson_corr]  # 将属性下标转为属性名
        pearson_corr.sort(key=lambda x: x[2], reverse=True)
        kendall_corr = [[attr_name[i[0]], attr_name[i[1]], i[2]] for i in kendall_corr]  # 将属性下标转为属性名
        kendall_corr.sort(key=lambda x: x[2], reverse=True)
        spearman_corr = [[attr_name[i[0]], attr_name[i[1]], i[2]] for i in spearman_corr]  # 将属性下标转为属性名
        spearman_corr.sort(key=lambda x: x[2], reverse=True)

        stat_data_quality = []  # 对表格数据进行质量检测，得到基本统计信息
        for key, val in excelproc.statistics_data_check().to_dict().items():
            stat_data_quality.append({key.replace('.', '').replace('$', ''): val})

        stat_data_quality_name, res = models.SavaData('stat_data_quality_' + data_name, stat_data_quality, True,
                                                      host=HOST, port=PORT, database=DATABASE)

        algo_data_quality = []  # 检测表格数据质量，得到算法检测结果
        for key, val in excelproc.algorithm_data_check().items():
            algo_data_quality.append({key: val})
        algo_data_quality_name, res = models.SavaData('algo_data_quality_' + data_name, algo_data_quality, True,
                                                      host=HOST, port=PORT, database=DATABASE)

        eudist_data_quality = []  # 检测表格数据质量，得到算法检测结果
        for key, val in excelproc.eudist_data_check().items():
            eudist_data_quality.append({'NO': key, 'count': val})
        eudist_data_quality_name, res = models.SavaData('eudist_data_quality_' + data_name, eudist_data_quality, True,
                                                        host=HOST, port=PORT, database=DATABASE)

        stat = models.ReadData(stat_data_quality_name, host=HOST, port=PORT, database=DATABASE)
        algo = models.ReadData(algo_data_quality_name, host=HOST, port=PORT, database=DATABASE)
        eudist = models.ReadData(eudist_data_quality_name, host=HOST, port=PORT, database=DATABASE)

        stat_dict = {}
        for i in stat:
            stat_dict.update(i)
        algo_dict = {}
        for i in algo:
            algo_dict.update(i)

        pca_result = excelproc.get_primary_components(2)
        pca_result_3 = excelproc.get_primary_components(3)

        return render(request, 'quality_control.html', {
            'dataname': data_name,
            'data': data,
            'stat': json.dumps(stat_dict),
            'algo': algo_dict,
            'eudist': json.dumps(eudist),
            'pearsonr': pearson_corr,
            'kendallr': kendall_corr,
            'spearmanr': spearman_corr,
            'col_start': si,
            'col_name': excelproc.col_name,
            'pca_result': pca_result,
            'pca_result3': pca_result_3,
        })


def quality_control(request, data_name):
    if request.method == 'POST':
        pass
    if request.method == 'GET':
        return render(request, 'quality_control_total.html', {
            'dataname': data_name,
        })


def quality_control_traceability(request, data_name):
    if request.method == 'POST':
        pass
    if request.method == 'GET':
        return render(request, 'quality_control_traceability.html', {
            'dataname': data_name
        })


def quality_control_precision(request, data_name):
    if request.method == 'POST':
        pass
    if request.method == 'GET':
        data = models.ReadData(data_name, host=HOST, port=PORT, database=DATABASE)
        excelproc = utils.excelProcessor(data)
        pearson_corr = excelproc.get_corr_coef('pearson')
        kendall_corr = excelproc.get_corr_coef('kendall')
        spearman_corr = excelproc.get_corr_coef('spearman')
        coef_determination_corr = excelproc.get_corr_coef('coef_determination')
        pointbiserialr_corr = excelproc.get_corr_coef('pointbiserialr')
        target_num = excelproc.get_dftarget_value_counts()
        attr_name = excelproc.col_name[:-1]
        pearson_corr = [[attr_name[i[0]], attr_name[i[1]], i[2]] for i in pearson_corr]  # 将属性下标转为属性名
        pearson_corr.sort(key=lambda x: x[2], reverse=True)
        kendall_corr = [[attr_name[i[0]], attr_name[i[1]], i[2]] for i in kendall_corr]  # 将属性下标转为属性名
        kendall_corr.sort(key=lambda x: x[2], reverse=True)
        spearman_corr = [[attr_name[i[0]], attr_name[i[1]], i[2]] for i in spearman_corr]  # 将属性下标转为属性名
        spearman_corr.sort(key=lambda x: x[2], reverse=True)
        coef_determination_corr = [[attr_name[i[0]], attr_name[i[1]], i[2]] for i in coef_determination_corr]
        coef_determination_corr.sort(key=lambda x: x[2], reverse=True)
        pointbiserialr_corr = [[attr_name[i[0]], attr_name[i[1]], i[2]] for i in pointbiserialr_corr]  # 将属性下标转为属性名
        pointbiserialr_corr.sort(key=lambda x: x[2], reverse=True)

        stat_data_quality = []  # 对表格数据进行质量检测，得到基本统计信息
        for key, val in excelproc.statistics_data_check().to_dict().items():
            stat_data_quality.append({key.replace('.', '').replace('$', ''): val})

        stat_data_quality_name, res = models.SavaData('stat_data_quality_' + data_name, stat_data_quality, True,
                                                      host=HOST, port=PORT, database=DATABASE)
        algo_data_quality = []  # 检测表格数据质量，得到算法检测结果
        for key, val in excelproc.algorithm_data_check().items():
            algo_data_quality.append({key: val})
        algo_data_quality_name, res = models.SavaData('algo_data_quality_' + data_name, algo_data_quality, True,
                                                      host=HOST, port=PORT, database=DATABASE)
        eudist_data_quality = []  # 检测表格数据质量，得到算法检测结果
        for key, val in excelproc.eudist_data_check().items():
            eudist_data_quality.append({'NO': key, 'count': val})
        eudist_data_quality_name, res = models.SavaData('eudist_data_quality_' + data_name, eudist_data_quality, True,
                                                        host=HOST, port=PORT, database=DATABASE)
        stat = models.ReadData(stat_data_quality_name, host=HOST, port=PORT, database=DATABASE)
        algo = models.ReadData(algo_data_quality_name, host=HOST, port=PORT, database=DATABASE)
        eudist = models.ReadData(eudist_data_quality_name, host=HOST, port=PORT, database=DATABASE)

        stat_dict = {}
        for i in stat:
            stat_dict.update(i)
        algo_dict = {}
        for i in algo:
            algo_dict.update(i)

        pca_result = excelproc.get_primary_components(2)
        pca_result_3 = excelproc.get_primary_components(3)
        return render(request, 'quality_control_precision.html', {
            'dataname': data_name,
            'data': data,
            'target_num': target_num,
            'stat': json.dumps(stat_dict),
            'algo': algo_dict,
            'eudist': json.dumps(eudist),
            'pearsonr': pearson_corr,
            'kendallr': kendall_corr,
            'spearmanr': spearman_corr,
            'coef_determination': coef_determination_corr,
            'pointbiserialr': pointbiserialr_corr,
            'col_start': si,
            'col_name': excelproc.col_name,
            'pca_result': pca_result,
            'pca_result3': pca_result_3,
        })


def quality_control_exploratory(request, data_name):
    if request.method == 'POST':
        data = models.ReadData(data_name, host=HOST, port=PORT, database=DATABASE)
        excelproc = utils.excelProcessor(data)
        machine_learning_algorithm = request.POST.get("machine_learning_algorithm")
        preprocessing = request.POST.get("preprocessing").strip()
        train_test_split = float(request.POST.get("train_test_split").strip())
        if machine_learning_algorithm == 'Ridge':
            tempInt = excelproc.dftarget.apply(float.is_integer).all()
            if tempInt:
                return render(request, 'quality_control_ex_result_error.html', {
                    'dataname': data_name,
                })
            alpha = float(request.POST.get("alpha").strip())
            fit_intercept = utils.str_to_bool(request.POST.get("fit_intercept").strip())
            normalize = utils.str_to_bool(request.POST.get("normalize").strip())
            copy_X = utils.str_to_bool(request.POST.get("copy_X").strip())
            max_iter = int(request.POST.get("max_iter").strip())
            tol = float(request.POST.get("tol").strip())
            Ridge_list = []
            for key, val in excelproc.get_Ridge(preprocessing, train_test_split, alpha, fit_intercept, normalize,
                                                copy_X, max_iter, tol).items():
                Ridge_list.append({key: val})
            _, _ = models.SavaData('Ridge_' + data_name, Ridge_list, True, host=HOST, port=PORT, database=DATABASE)
            return redirect(reverse('quality_control_ex_result', kwargs={
                'data_name': data_name,
                'method': machine_learning_algorithm,
            }))
        if machine_learning_algorithm == 'Lasso':
            tempInt = excelproc.dftarget.apply(float.is_integer).all()
            if tempInt:
                return render(request, 'quality_control_ex_result_error.html', {
                    'dataname': data_name,
                })
            alpha = float(request.POST.get("alpha").strip())
            fit_intercept = utils.str_to_bool(request.POST.get("fit_intercept").strip())
            normalize = utils.str_to_bool(request.POST.get("normalize").strip())
            precompute = utils.str_to_bool(request.POST.get("precompute").strip())
            copy_X = utils.str_to_bool(request.POST.get("copy_X").strip())
            max_iter = int(request.POST.get("max_iter").strip())
            tol = float(request.POST.get("tol").strip())
            warm_start = utils.str_to_bool(request.POST.get("warm_start").strip())
            positive = utils.str_to_bool(request.POST.get("positive").strip())
            Lasso_list = []
            for key, val in excelproc.get_Lasso(preprocessing, train_test_split, alpha, fit_intercept, normalize,
                                                copy_X, precompute, max_iter, tol, warm_start, positive).items():
                Lasso_list.append({key: val})
            _, _ = models.SavaData('Lasso_' + data_name, Lasso_list, True, host=HOST, port=PORT, database=DATABASE)
            return redirect(reverse('quality_control_ex_result', kwargs={
                'data_name': data_name,
                'method': machine_learning_algorithm,
            }))
        if machine_learning_algorithm == 'SVR':
            tempInt = excelproc.dftarget.apply(float.is_integer).all()
            if tempInt:
                return render(request, 'quality_control_ex_result_error.html', {
                    'dataname': data_name,
                })
            kernel = request.POST.get("kernel").strip()
            degree = int(request.POST.get("degree").strip())
            gamma = request.POST.get("gamma").strip()
            coef0 = float(request.POST.get("coef0").strip())
            tol = float(request.POST.get("tol").strip())
            C = float(request.POST.get("C").strip())
            epsilon = float(request.POST.get("epsilon").strip())
            shrinking = utils.str_to_bool(request.POST.get("shrinking").strip())
            cache_size = float(request.POST.get("cache_size").strip())
            verbose = utils.str_to_bool(request.POST.get("verbose").strip())
            max_iter = int(request.POST.get("max_iter").strip())
            SVR_list = []
            for key, val in excelproc.get_SVR(preprocessing, train_test_split, kernel, degree, gamma, coef0, tol,
                                              C, epsilon, shrinking, cache_size, verbose, max_iter).items():
                SVR_list.append({key: val})
            _, _ = models.SavaData('SVR_' + data_name, SVR_list, True, host=HOST, port=PORT, database=DATABASE)
            return redirect(reverse('quality_control_ex_result', kwargs={
                'data_name': data_name,
                'method': machine_learning_algorithm,
            }))
        if machine_learning_algorithm == 'LogisticRegression':
            tempInt = excelproc.dftarget.apply(float.is_integer).all()
            if bool(1 - tempInt):
                return render(request, 'quality_control_ex_result_error.html', {
                    'dataname': data_name,
                })
            penalty = request.POST.get("penalty").strip()
            dual = utils.str_to_bool(request.POST.get("dual"))
            tol = float(request.POST.get("tol").strip())
            C = float(request.POST.get("C").strip())
            fit_intercept = utils.str_to_bool(request.POST.get("fit_intercept").strip())
            intercept_scaling = float(request.POST.get("intercept_scaling").strip())
            solver = request.POST.get("solver").strip()
            max_iter = int(request.POST.get("max_iter").strip())
            multi_class = request.POST.get("multi_class").strip()
            verbose = int(request.POST.get("verbose").strip())
            warm_start = utils.str_to_bool(request.POST.get("warm_start").strip())
            LR_list = []
            for key, val in excelproc.get_LogisticRegression(preprocessing, train_test_split, penalty, dual, tol, C,
                                                             fit_intercept, intercept_scaling, solver, max_iter,
                                                             multi_class, verbose, warm_start).items():
                LR_list.append({key: val})
            _, _ = models.SavaData('LogisticRegression_' + data_name, LR_list, True, host=HOST, port=PORT,
                                   database=DATABASE)
            return redirect(reverse('quality_control_ex_result', kwargs={
                'data_name': data_name,
                'method': machine_learning_algorithm,
            }))
        if machine_learning_algorithm == 'SVC':
            tempInt = excelproc.dftarget.apply(float.is_integer).all()
            if bool(1 - tempInt):
                return render(request, 'quality_control_ex_result_error.html', {
                    'dataname': data_name,
                })
            C = float(request.POST.get("C").strip())
            kernel = request.POST.get("kernel").strip()
            degree = int(request.POST.get("degree").strip())
            gamma = request.POST.get("gamma").strip()
            coef0 = float(request.POST.get("coef0").strip())
            shrinking = utils.str_to_bool(request.POST.get("shrinking").strip())
            probability = utils.str_to_bool(request.POST.get("probability").strip())
            tol = float(request.POST.get("tol").strip())
            cache_size = float(request.POST.get("cache_size").strip())
            verbose = utils.str_to_bool(request.POST.get("verbose").strip())
            max_iter = int(request.POST.get("max_iter").strip())
            decision_function_shape = request.POST.get("decision_function_shape").strip()
            break_ties = utils.str_to_bool(request.POST.get("break_ties").strip())
            SVC_list = []
            for key, val in excelproc.get_SVC(preprocessing, train_test_split, C, kernel, degree, gamma, coef0,
                                              shrinking, probability, tol, cache_size, verbose, max_iter,
                                              decision_function_shape, break_ties).items():
                SVC_list.append({key: val})
            _, _ = models.SavaData('SVC_' + data_name, SVC_list, True, host=HOST, port=PORT,
                                   database=DATABASE)
            return redirect(reverse('quality_control_ex_result', kwargs={
                'data_name': data_name,
                'method': machine_learning_algorithm,
            }))
        if machine_learning_algorithm == 'KNeighborsClassifier':
            tempInt = excelproc.dftarget.apply(float.is_integer).all()
            if bool(1 - tempInt):
                return render(request, 'quality_control_ex_result_error.html', {
                    'dataname': data_name,
                })
            n_neighbors = int(request.POST.get("n_neighbors").strip())
            weights = request.POST.get("weights").strip()
            algorithm = request.POST.get("algorithm").strip()
            leaf_size = int(request.POST.get("leaf_size").strip())
            p = int(request.POST.get("p").strip())
            KNN_list = []
            for key, val in excelproc.get_KNeighborsClassifier(preprocessing, train_test_split, n_neighbors, weights,
                                                               algorithm,
                                                               leaf_size, p).items():
                KNN_list.append({key: val})
            _, _ = models.SavaData('KNeighborsClassifier_' + data_name, KNN_list, True, host=HOST, port=PORT,
                                   database=DATABASE)
            return redirect(reverse('quality_control_ex_result', kwargs={
                'data_name': data_name,
                'method': machine_learning_algorithm,
            }))

    if request.method == 'GET':
        return render(request, 'quality_control_exploratory.html', {
            'dataname': data_name,
        })


def quality_control_ex_result(request, data_name, method):
    if request.method == 'POST':
        pass
    if request.method == 'GET':
        data = models.ReadData(data_name, host=HOST, port=PORT, database=DATABASE)
        mlal_res = models.ReadData(method + "_" + data_name, host=HOST, port=PORT, database=DATABASE)
        list1 = ['Ridge', 'Lasso', 'SVR']
        list2 = ['LogisticRegression', 'SVC', 'KNeighborsClassifier']
        if list1.count(method) > 0:
            return render(request, 'quality_control_ex_result.html', {
                'dataname': data_name,
                'data': data,
                'mlal_res': mlal_res,
            })
        elif list2.count(method) > 0:
            return render(request, 'quality_control_ex_result_second.html', {
                'dataname': data_name,
                'data': data,
                'mlal_res': mlal_res,
            })


def download(request, name):
    if request.method == 'GET':
        data = models.ReadData(name, host=HOST, port=PORT, database=DATABASE)
        dataj = pd.read_json(json.dumps(data))
        WFP = os.path.join(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'excel_file'),
                           str(name) + '_downloaded')
        # WFP = '././excel_file/' + str(name)
        dataj.to_excel(WFP, index=False)
        # res = FileResponse(file)
        # res['Content-Type'] = 'application/octet-stream'
        # res['Content-Disposition'] = 'attachment;filename="' + str(name) + '"'
        return FileResponse(open(WFP, 'rb'))


def chooseDomainKnowledgeEmbeddingMethod(request, data_name):
    if request.method == 'POST':
        pass
    if request.method == 'GET':
        return render(request, 'embed_domain_knowledge.html', {'dataname': data_name})


def featureselection(request, data_name):
    # TODO: use async while users submit the feature selection request
    if request.method == 'POST':
        check_list = request.POST.getlist('checkbox_list')

        features_to_retain = [{'name': feature_name} for feature_name in check_list]
        if features_to_retain:
            ftr_name, res = models.SavaData('custom_retain_features_' + data_name, features_to_retain, True, HOST, PORT,
                                            DATABASE)
        verbose_feature = models.ReadData('verbose_attr_' + data_name, HOST, PORT, DATABASE)

        origin_data = utils.excelProcessor(models.ReadData(data_name, HOST, PORT, DATABASE))
        sample_num = origin_data.count

        features_to_retain_idx = [origin_data.col_name[:-1].index(e['name']) for e in features_to_retain]
        verbose_feature_idx = [origin_data.col_name[:-1].index(e['name']) for e in verbose_feature]
        # for e in features_to_retain:
        #     features_to_retain_idx.append(origin_data.col_name[:-1].index(e['name']))
        print(features_to_retain_idx, verbose_feature_idx)

        abnornal_sample_idx = [el['NO'] for el in
                               models.ReadData('eudist_data_quality_' + data_name, host=HOST, port=PORT,
                                               database=DATABASE)]

        index_of_sets = [[1, 3, 6, 14, 24, 28, 29, 38, 43, 48],
                         [0, 5, 8, 15, 16, 25, 30, 31, 39, 44],
                         [2, 10, 11, 17, 18, 26, 32, 33, 40, 45],
                         [9, 12, 13, 19, 20, 27, 34, 35, 41, 46],
                         [4, 7, 21, 22, 23, 36, 37, 42, 47, 49]]

        bpso_fk = BPSO_FK.BPSO_FK(origin_data, 100, 0.01, 3, features_to_retain_idx, verbose_feature_idx,
                                  index_of_sets)
        ml_model, res, rmse, r2, evo_record = bpso_fk.evolve()
        print('model: ', ml_model)
        print('res: ', res)

        res = [int(e) for e in res]
        method = 'LinearRegression'

        models.SavaData('fs_result_' + data_name,
                        [{
                            'method': method,
                            'res': res,
                            'coef': list(ml_model.coef_),
                            'intercept': ml_model.intercept_,
                            'rmse': rmse,
                            'r2': r2
                        }], True, HOST, PORT, DATABASE)
        ml_method = models.MachineLearningMethods(method_name=method)
        ml_method.save()
        print(evo_record)
        return render(request, 'show_feature_select.html',
                      {
                          'dataname': data_name,
                          'retainedfeatures': features_to_retain,
                          'verbosefeatures': verbose_feature,
                          'result': [origin_data.col_name[:-1][i] for i in range(len(origin_data.col_name[:-1])) if
                                     i in res],
                          'rmse': rmse,
                          'r2': r2,
                          'evorecord': evo_record
                      })

    if request.method == 'GET':
        data = models.ReadData(data_name, HOST, PORT, DATABASE)  # 读原始数据
        excelproc = utils.excelProcessor(data)

        verbose_attrs = models.ReadData('verbose_attr_' + data_name, HOST, PORT, DATABASE)  # 读标记的冗余属性
        features_to_select = excelproc.col_name[:-1]  # 全部属性
        for verbose_attr in verbose_attrs:  # 从筛选冗余属性后的属性中，选择自定义保留属性
            features_to_select.remove(verbose_attr['name'])

        return render(request, 'custom_retain_features.html',
                      {
                          'dataname': data_name,
                          'featurenames': features_to_select
                      })


def featureselectionBycontributionRules(request, data_name):
    if request.method == 'POST':
        pass
    if request.method == 'GET':
        return render(request, 'testhtml.html', {'dataname': data_name})


def featureselectionByScore(request, data_name):
    if request.method == 'POST':
        pass
    if request.method == 'GET':
        return render(request, 'testhtml.html', {'dataname': data_name})


def machinelearning(request, data_name, from_where):
    """
    :param request:
    :param data_name:
    :param from_where: 用于判断从哪个页面进入本页
    :return:
    """
    global model
    if request.method == 'POST':
        if from_where == 'featureselection':
            radio_list = request.POST.getlist('radio_list')
            fs_result_all = models.ReadData('fs_result_' + data_name, HOST, PORT, DATABASE)
            fs_result = None
            for res_i in fs_result_all:
                if res_i.get('method', None) in radio_list:
                    fs_result = res_i

            origin_data = utils.excelProcessor(models.ReadData(data_name, HOST, PORT, DATABASE))
            feature_names = origin_data.col_name

            selected_features = [feature_names[i] for i in fs_result.get('res', None)]
            feture_coef = list(zip(selected_features, fs_result.get('coef', None)))

            return render(request, 'show_machine_learning.html',
                          {
                              'dataname': data_name,
                              'ml_method': fs_result.get('method', None),
                              'coef': fs_result.get('coef', None),
                              'intercept': fs_result.get('intercept', None),
                              'rmse': fs_result.get('rmse', None),
                              'r2': fs_result.get('r2', None),
                              'selected_features': selected_features,
                              'fc': feture_coef,
                              'from_where': from_where,
                          })
        # return HttpResponse('Success! You have chosen {}'.format(radio_list))
        if from_where == 'qualitycontrol':
            radio_list = request.POST.getlist('radio_list')
            model = None
            if radio_list[0] == 'LinearRegression':
                from sklearn.linear_model import LinearRegression
                model = LinearRegression()
                origin_data = utils.excelProcessor(models.ReadData(data_name, HOST, PORT, DATABASE))
                model.fit(origin_data.X, origin_data.Y)
            if radio_list[0] == 'Ridge':
                from sklearn.linear_model import Ridge
                model = Ridge()
                origin_data = utils.excelProcessor(models.ReadData(data_name, HOST, PORT, DATABASE))
                model.fit(origin_data.X, origin_data.Y)
            if radio_list[0] == 'SVR':
                from sklearn.svm import SVR
                model = SVR()
                origin_data = utils.excelProcessor(models.ReadData(data_name, HOST, PORT, DATABASE))
                model.fit(origin_data.X, origin_data.Y)

            return render(request, 'show_machine_learning.html',
                          {
                              'dataname': data_name,
                              'ml_method': model,
                              'from_where': from_where,
                          })

    if request.method == 'GET':
        if from_where == 'featureselection':
            ml_methods_orm = models.MachineLearningMethods.objects.all()  # 查询orm和mongodb中的ml方法，统一

            fs_res = models.ReadData('fs_result_' + data_name, HOST, PORT, DATABASE)
            ml_methods_mdb = [doc.get('method', None) for doc in fs_res] if fs_res else []

            print(ml_methods_orm)
            print(ml_methods_mdb)
            for model_item in ml_methods_orm:
                if model_item in ml_methods_mdb:
                    continue
                else:
                    models.MachineLearningMethods.objects.filter(method_name=model_item.method_name).delete()

            # for data_item in ml_methods_mdb:
            #     if models.MachineLearningMethods.objects.filter(method_name=data_item):
            #         continue
            #     else:
            #         res = models.RmDoc({'method': data_item}, 'fs_result_' + data_name, HOST, PORT, DATABASE)

            return render(request, 'machine_learning.html',
                          {
                              'dataname': data_name,
                              'ml_methods': ml_methods_mdb,
                              'from_where': from_where,
                          })
        if from_where == 'qualitycontrol':
            return render(request, 'machine_learning.html',
                          {
                              'dataname': data_name,
                              'from_where': from_where,
                              'ml_methods': ['LinearRegression', 'Ridge', 'SVR'],
                          })


def predict(request, data_name, method_name, from_where):
    if request.method == 'POST':
        if from_where == 'featureselection':
            fileinput = request.FILES.get('input-excel')  # read file from <input name="input-excel">
            fileinputname = fileinput.name  # get file name
            excelproc = utils.excelProcessor(fileinput)  # preprocess the file uploaded

            origin_data_to_predict = excelproc.df
            for col in origin_data_to_predict:
                origin_data_to_predict.rename(columns={col: col.replace('.', '').replace('$', '')}, inplace=True)

            fs_result_all = models.ReadData('fs_result_' + data_name, HOST, PORT, DATABASE)
            fs_result = None
            for res_i in fs_result_all:
                if res_i.get('method', None) == method_name:
                    fs_result = res_i

            origin_data = utils.excelProcessor(models.ReadData(data_name, HOST, PORT, DATABASE))
            feature_names = origin_data.col_name
            selected_features = [feature_names[i] for i in fs_result.get('res', None)]

            data_to_predict = origin_data_to_predict.loc[:, selected_features].values

            targets = []
            coef = fs_result.get('coef', None)
            for sample in data_to_predict:
                target = fs_result.get('intercept', None)
                for idx in range(len(sample)):
                    target += sample[idx] * coef[idx]
                targets.append(target)

            origin_data_to_predict.insert(0, 'predict', targets)
            print(origin_data_to_predict)

            return render(request, 'predict_page.html',
                          {
                              'dataname': data_name,
                              'selected_features': selected_features,
                              'coef': fs_result.get('coef', None),
                              'intercept': fs_result.get('intercept', None),
                              'uploadtopredict': 'True',
                              'uploadonly': 'False',
                              'predictresult': origin_data_to_predict.T.to_dict(),
                          })
        if from_where == 'qualitycontrol':
            fileinput = request.FILES.get('input-excel')  # read file from <input name="input-excel">
            fileinputname = fileinput.name  # get file name
            excelproc = utils.excelProcessor(fileinput)  # preprocess the file uploaded

            origin_data_to_predict = excelproc.df
            for col in origin_data_to_predict:
                origin_data_to_predict.rename(columns={col: col.replace('.', '').replace('$', '')}, inplace=True)

            data_to_predict = excelproc.X

            targets = model.predict(data_to_predict)
            print(targets)
            origin_data_to_predict.insert(0, 'predict', targets)
            return render(request, 'predict_page.html',
                          {
                              'dataname': data_name,
                              'selected_features': [],
                              'coef': [],
                              'intercept': [],
                              'uploadtopredict': 'True',
                              'predictresult': origin_data_to_predict.T.to_dict(),
                          })
    if request.method == 'GET':
        if from_where == 'featureselection':
            fs_result_all = models.ReadData('fs_result_' + data_name, HOST, PORT, DATABASE)
            fs_result = None
            for res_i in fs_result_all:
                if res_i.get('method', None) == method_name:
                    fs_result = res_i

            origin_data = utils.excelProcessor(models.ReadData(data_name, HOST, PORT, DATABASE))
            feature_names = origin_data.col_name

            selected_features = [feature_names[i] for i in fs_result.get('res', None)]
            feture_coef = list(zip(selected_features, fs_result.get('coef', None)))
            return render(request, 'predict_page.html',
                          {
                              'dataname': data_name,
                              'selected_features': selected_features,
                              'coef': fs_result.get('coef', None),
                              'intercept': fs_result.get('intercept', None),
                              'uploadtopredict': 'False',
                              'uploadonly': 'False',
                          })
        if from_where == 'qualitycontrol':
            return render(request, 'predict_page.html',
                          {
                              'dataname': data_name,
                              'selected_features': [],
                              'coef': [],
                              'intercept': [],
                              'uploadtopredict': 'False',
                              'uploadonly': 'True'
                          })
